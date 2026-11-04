"""Golden-dataset regression suite for the RFQ extraction pipeline.

Run before changing a prompt, the parser, or the extraction model:

    python -m pytest evals/ -s

Metrics tracked (printed as a summary by the aggregate test):
  - Field accuracy: exact match on material / size / schedule / quantity,
    per expected line item.
  - Hallucination rate: extracted items with no matching expected item.
  - Safety fallthrough rate: items the dataset marks should_flag (invalid
    spec, unknown grade, exotic alloy, missing quantity) that the pipeline
    let through without a human-review flag. This one has to stay at zero.
"""
import json
import os

import pytest
from sqlmodel import Session

from app.db import engine
from app.extraction import extract
from app.validation import normalize_schedule, validate_and_score_item

GOLDEN = json.load(open(os.path.join(os.path.dirname(__file__), "golden_rfqs.json")))
CASES = {c["id"]: c for c in GOLDEN}
FIELDS = ["material_grade", "nominal_size", "schedule_or_rating", "quantity"]


def run_pipeline(raw_input: str) -> list[dict]:
    result, _extractor = extract(raw_input)
    out = []
    with Session(engine) as session:
        for item in result.line_items:
            outcome = validate_and_score_item(item, session)
            out.append({
                "material_grade": outcome["normalized_material"] or "",
                "nominal_size": outcome["normalized_size"] or "",
                "schedule_or_rating": outcome["normalized_schedule"],
                "quantity": item.quantity,
                "requires_review": outcome["requires_review"],
            })
    return out


def score_case(case: dict) -> dict:
    extracted = run_pipeline(case["raw_input"])
    expected = case["expected_line_items"]

    field_hits = {f: 0 for f in FIELDS}
    field_total = {f: 0 for f in FIELDS}
    fallthroughs = 0
    flaggable = 0

    for i, exp in enumerate(expected):
        got = extracted[i] if i < len(extracted) else None
        for f in FIELDS:
            field_total[f] += 1
            if got is None:
                continue
            want = exp.get(f)
            have = got[f]
            if f == "schedule_or_rating":
                want = normalize_schedule(want) if want else None
            if have == want:
                field_hits[f] += 1
        if exp.get("should_flag"):
            flaggable += 1
            if got is not None and not got["requires_review"]:
                fallthroughs += 1

    hallucinated = max(0, len(extracted) - len(expected))
    return {
        "field_hits": field_hits,
        "field_total": field_total,
        "hallucinated": hallucinated,
        "extracted": len(extracted),
        "fallthroughs": fallthroughs,
        "flaggable": flaggable,
    }


@pytest.mark.parametrize("case_id", list(CASES))
def test_case_line_items(case_id):
    case = CASES[case_id]
    result = score_case(case)
    total_fields = sum(result["field_total"].values())
    hits = sum(result["field_hits"].values())
    if total_fields == 0:
        return  # case expects no line items; the count assertion above covers it
    assert result["extracted"] == len(case["expected_line_items"]), (
        f"{case_id}: extracted {result['extracted']} items, "
        f"expected {len(case['expected_line_items'])}"
    )
    assert hits / max(total_fields, 1) >= 0.75, (
        f"{case_id}: field accuracy {hits}/{total_fields} — {result['field_hits']}"
    )
    assert result["fallthroughs"] == 0, f"{case_id}: invalid spec reached auto-approve"


def test_eval_summary():
    totals = {"hits": {f: 0 for f in FIELDS}, "total": {f: 0 for f in FIELDS},
              "hallucinated": 0, "extracted": 0, "fallthroughs": 0, "flaggable": 0}
    for case in GOLDEN:
        r = score_case(case)
        for f in FIELDS:
            totals["hits"][f] += r["field_hits"][f]
            totals["total"][f] += r["field_total"][f]
        totals["hallucinated"] += r["hallucinated"]
        totals["extracted"] += r["extracted"]
        totals["fallthroughs"] += r["fallthroughs"]
        totals["flaggable"] += r["flaggable"]

    print("\n--- RFQ-Flow eval summary (golden dataset, rules fallback extractor) ---")
    for f in FIELDS:
        acc = totals["hits"][f] / max(totals["total"][f], 1)
        print(f"  {f:20s} {acc:.1%}  ({totals['hits'][f]}/{totals['total'][f]})")
    overall = sum(totals["hits"].values()) / max(sum(totals["total"].values()), 1)
    hallucination_rate = totals["hallucinated"] / max(totals["extracted"], 1)
    fallthrough_rate = totals["fallthroughs"] / max(totals["flaggable"], 1)
    print(f"  {'OVERALL':20s} {overall:.1%}")
    print(f"  hallucination rate       {hallucination_rate:.1%}")
    print(f"  safety fallthrough rate  {fallthrough_rate:.1%}")

    assert hallucination_rate == 0
    assert fallthrough_rate == 0
    assert overall >= 0.80
