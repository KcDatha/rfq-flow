import io
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select

from .db import engine, init_db
from .models import MaterialGrade, PipeSchedule, RFQLineItem, RFQSubmission
from .pricing import estimate_unit_price
from .schemas import ExtractedLineItem
from .seed import seed_catalog
from .validation import validate_and_score_item


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        seed_catalog(session)
    yield


app = FastAPI(title="RFQ-Flow", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Intake ------------------------------------------------------------------

class RFQIn(BaseModel):
    raw_text: str
    customer_name: Optional[str] = None


def _process(session: Session, sub: RFQSubmission) -> RFQSubmission:
    # Imported here, not at module top: the graph module pulls in
    # langgraph, whose import dominates cold-start time. Read endpoints
    # and page loads should not pay for it; only submissions should.
    from .graph import process_submission

    return process_submission(session, sub)


def _submission_out(session: Session, sub: RFQSubmission) -> dict:
    items = session.exec(
        select(RFQLineItem).where(RFQLineItem.rfq_id == sub.rfq_id)
    ).all()
    data = sub.model_dump()
    data["line_items"] = [i.model_dump() for i in items]
    return data


@app.post("/rfqs")
def submit_rfq(payload: RFQIn):
    with Session(engine) as session:
        sub = RFQSubmission(raw_text=payload.raw_text, customer_name=payload.customer_name)
        session.add(sub)
        session.commit()
        session.refresh(sub)
        sub = _process(session, sub)
        return _submission_out(session, sub)


@app.post("/rfqs/upload")
async def upload_rfq(file: UploadFile = File(...)):
    content = await file.read()
    if file.filename and file.filename.lower().endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    else:
        text = content.decode("utf-8", errors="replace")
    if not text.strip():
        raise HTTPException(400, "Could not read any text from that file.")
    with Session(engine) as session:
        sub = RFQSubmission(raw_text=text, source_filename=file.filename)
        session.add(sub)
        session.commit()
        session.refresh(sub)
        sub = _process(session, sub)
        return _submission_out(session, sub)


# --- Reads ---------------------------------------------------------------------

@app.get("/rfqs")
def list_rfqs():
    with Session(engine) as session:
        subs = session.exec(
            select(RFQSubmission).order_by(RFQSubmission.created_at.desc())
        ).all()
        return [_submission_out(session, s) for s in subs]


@app.get("/rfqs/{rfq_id}")
def get_rfq(rfq_id: str):
    with Session(engine) as session:
        sub = session.get(RFQSubmission, rfq_id)
        if not sub:
            raise HTTPException(404, "RFQ not found")
        return _submission_out(session, sub)


@app.get("/review-queue")
def review_queue():
    with Session(engine) as session:
        items = session.exec(
            select(RFQLineItem).where(
                RFQLineItem.requires_human_review == True,  # noqa: E712
                RFQLineItem.reviewed == False,  # noqa: E712
            )
        ).all()
        out = []
        for item in items:
            sub = session.get(RFQSubmission, item.rfq_id)
            row = item.model_dump()
            row["customer_name"] = sub.customer_name if sub else None
            row["rfq_status"] = sub.status if sub else None
            out.append(row)
        return out


@app.get("/catalog/materials")
def catalog_materials():
    with Session(engine) as session:
        return [m.model_dump() for m in session.exec(select(MaterialGrade)).all()]


@app.get("/catalog/schedules")
def catalog_schedules():
    with Session(engine) as session:
        return [s.model_dump() for s in session.exec(select(PipeSchedule)).all()]


# --- Human review ----------------------------------------------------------------

class ReviewIn(BaseModel):
    product_category: Optional[str] = None
    extracted_material: Optional[str] = None
    extracted_size: Optional[str] = None
    extracted_schedule: Optional[str] = None
    quantity: Optional[int] = None
    unit_price: Optional[float] = None


@app.patch("/review/{item_id}")
def review_item(item_id: str, payload: ReviewIn):
    with Session(engine) as session:
        item = session.get(RFQLineItem, item_id)
        if not item:
            raise HTTPException(404, "Line item not found")

        changed = False
        for field in ("product_category", "extracted_material", "extracted_size",
                      "extracted_schedule", "quantity"):
            value = getattr(payload, field)
            if value is not None:
                setattr(item, field, value)
                changed = True
        if payload.unit_price is not None:
            item.unit_price = payload.unit_price

        if changed:
            # Re-run the deterministic checks against the corrected values so
            # the confidence score reflects what the rep actually approved.
            probe = ExtractedLineItem(
                raw_text=item.raw_line_text,
                product_category=item.product_category or "",
                material_grade=item.extracted_material or "",
                nominal_size=item.extracted_size or "",
                schedule_or_rating=item.extracted_schedule,
                quantity=item.quantity or 0,
                unit_of_measure=item.unit_of_measure,
            )
            outcome = validate_and_score_item(probe, session)
            item.confidence_score = outcome["confidence"]
            item.validation_notes = outcome["flags"]
            item.requires_human_review = outcome["requires_review"]

        item.reviewed = True
        session.add(item)
        session.commit()

        # If nothing in this RFQ still needs review, move it out of the queue.
        sub = session.get(RFQSubmission, item.rfq_id)
        remaining = session.exec(
            select(RFQLineItem).where(
                RFQLineItem.rfq_id == item.rfq_id,
                RFQLineItem.requires_human_review == True,  # noqa: E712
                RFQLineItem.reviewed == False,  # noqa: E712
            )
        ).all()
        if sub and not remaining and sub.status == "HUMAN_REVIEW":
            sub.status = "REVIEWED"
            session.add(sub)
            session.commit()
        session.refresh(item)
        return item.model_dump()


# --- Quoting -----------------------------------------------------------------

@app.post("/rfqs/{rfq_id}/quote")
def generate_quote(rfq_id: str):
    with Session(engine) as session:
        sub = session.get(RFQSubmission, rfq_id)
        if not sub:
            raise HTTPException(404, "RFQ not found")
        items = session.exec(
            select(RFQLineItem).where(RFQLineItem.rfq_id == rfq_id)
        ).all()
        if not items:
            raise HTTPException(400, "RFQ has no line items to quote")

        lines, total = [], 0.0
        for item in items:
            if item.unit_price is None:
                grade = session.get(MaterialGrade, item.extracted_material or "")
                item.unit_price = estimate_unit_price(
                    item.product_category, item.extracted_size,
                    grade.category if grade else None,
                )
                session.add(item)
            line_total = round(item.unit_price * (item.quantity or 0), 2)
            total += line_total
            lines.append({
                "item_id": item.item_id,
                "description": item.raw_line_text,
                "quantity": item.quantity,
                "unit_of_measure": item.unit_of_measure,
                "unit_price": item.unit_price,
                "line_total": line_total,
            })
        sub.status = "QUOTED"
        session.add(sub)
        session.commit()
        return {
            "rfq_id": rfq_id,
            "customer_name": sub.customer_name,
            "lines": lines,
            "total": round(total, 2),
        }
