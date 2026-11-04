"""The RFQ pipeline as a LangGraph graph.

    extract -> validate -> route

Extraction is the only node that talks to an LLM (and it degrades to a
rules parser without a key). Validation is deterministic SQL + rules.
Routing is a status decision: everything clean auto-approves, anything
flagged goes to the human review queue.
"""
from typing import Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlmodel import Session

from . import extraction
from .db import engine
from .models import RFQLineItem, RFQSubmission
from .schemas import ExtractedLineItem
from .validation import validate_and_score_item


class RFQState(TypedDict):
    raw_text: str
    customer_name: Optional[str]
    extractor_used: Optional[str]
    extracted_items: list[ExtractedLineItem]
    validated_items: list[dict]
    status: str


def extract_node(state: RFQState) -> dict:
    result, extractor_name = extraction.extract(state["raw_text"])
    return {
        "extracted_items": result.line_items,
        "customer_name": result.customer_name or state.get("customer_name"),
        "extractor_used": extractor_name,
    }


def validate_node(state: RFQState) -> dict:
    validated = []
    with Session(engine) as session:
        for item in state["extracted_items"]:
            outcome = validate_and_score_item(item, session)
            validated.append({"item": item, **outcome})
    return {"validated_items": validated}


def route_node(state: RFQState) -> dict:
    items = state["validated_items"]
    if items and all(not v["requires_review"] for v in items):
        status = "AUTO_APPROVED"
    else:
        status = "HUMAN_REVIEW"
    return {"status": status}


def build_graph():
    graph = StateGraph(RFQState)
    graph.add_node("extract", extract_node)
    graph.add_node("validate", validate_node)
    graph.add_node("route", route_node)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "validate")
    graph.add_edge("validate", "route")
    graph.add_edge("route", END)
    return graph.compile()


_pipeline = None


def get_pipeline():
    """Compile the graph on first use, not at import time.

    Importing langgraph and compiling the graph costs seconds of CPU; on
    serverless that tax was paid by every cold start, including plain
    page loads and GET requests that never touch the pipeline. Only a
    submission should pay it, and only once per instance.
    """
    global _pipeline
    if _pipeline is None:
        _pipeline = build_graph()
    return _pipeline


def process_submission(session: Session, submission: RFQSubmission) -> RFQSubmission:
    """Run the graph for one submission and persist the results."""
    final = get_pipeline().invoke(
        {
            "raw_text": submission.raw_text,
            "customer_name": submission.customer_name,
            "extractor_used": None,
            "extracted_items": [],
            "validated_items": [],
            "status": "PENDING",
        }
    )

    submission.customer_name = final["customer_name"]
    submission.extractor_used = final["extractor_used"]
    submission.status = final["status"]

    for v in final["validated_items"]:
        item: ExtractedLineItem = v["item"]
        session.add(
            RFQLineItem(
                rfq_id=submission.rfq_id,
                raw_line_text=item.raw_text,
                product_category=item.product_category,
                extracted_material=v["normalized_material"],
                extracted_size=v["normalized_size"],
                extracted_schedule=v["normalized_schedule"],
                quantity=item.quantity,
                unit_of_measure=item.unit_of_measure,
                confidence_score=v["confidence"],
                requires_human_review=v["requires_review"],
                validation_notes=v["flags"],
            )
        )
    session.add(submission)
    session.commit()
    session.refresh(submission)
    return submission
