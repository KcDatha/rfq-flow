"""Deterministic validation + confidence scoring.

No LLM here on purpose: an item either matches the catalog or it doesn't,
and the score has to be reproducible when a sales rep asks why something
was flagged.
"""
from sqlmodel import Session, select

from .config import settings
from .models import MaterialGrade, PipeSchedule
from .schemas import ExtractedLineItem

SCHEDULE_ALIASES = {
    "40": "SCH 40", "SCH40": "SCH 40", "S40": "SCH 40",
    "80": "SCH 80", "SCH80": "SCH 80", "S80": "SCH 80",
    "160": "SCH 160", "SCH160": "SCH 160",
    "STD": "STD", "STANDARD": "STD",
    "XS": "XS", "XH": "XS",
}


def normalize_schedule(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip().upper().replace(" ", "")
    if cleaned in SCHEDULE_ALIASES:
        return SCHEDULE_ALIASES[cleaned]
    if cleaned.startswith("SCH"):
        return "SCH " + cleaned[3:]
    return raw.strip().upper()


def normalize_size(raw: str | None) -> str | None:
    if not raw:
        return None
    size = raw.strip().replace("″", '"').replace("”", '"')
    if not size.endswith('"'):
        size += '"'
    return size


def validate_and_score_item(item: ExtractedLineItem, session: Session) -> dict:
    confidence = 1.0
    flags: list[str] = []

    material = (item.material_grade or "").strip().upper()
    size = normalize_size(item.nominal_size)
    schedule = normalize_schedule(item.schedule_or_rating)

    # 1. Deterministic catalog match on the material grade.
    mat_match = session.exec(
        select(MaterialGrade).where(MaterialGrade.grade_id == material)
    ).first()
    if not mat_match:
        confidence -= 0.35
        flags.append(f"Unknown material grade: '{item.material_grade}'. Catalog lookup failed.")

    # 2. Engineering rule check: does this size/schedule combination exist?
    if item.product_category and item.product_category.lower() == "pipe":
        sched_match = None
        if size and schedule:
            sched_match = session.exec(
                select(PipeSchedule).where(
                    PipeSchedule.nominal_pipe_size == size,
                    PipeSchedule.schedule_name == schedule,
                )
            ).first()
        if not sched_match:
            confidence -= 0.40
            flags.append(
                f"Invalid size/schedule combination: {item.nominal_size} {item.schedule_or_rating}."
            )

    # 3. Exotic alloys always get a human sanity check (they're expensive mistakes).
    if mat_match and mat_match.is_exotic:
        confidence -= 0.15
        flags.append("Exotic alloy detected; flagged for human sales rep verification.")

    # 4. Missing quantity is a data problem, not a spec problem, but it blocks quoting.
    if not item.quantity or item.quantity <= 0:
        confidence -= 0.20
        flags.append("Quantity missing or invalid.")

    requires_review = confidence < settings.review_threshold or len(flags) > 0
    return {
        "confidence": round(max(0.0, confidence), 3),
        "flags": flags,
        "requires_review": requires_review,
        "normalized_material": material or None,
        "normalized_size": size,
        "normalized_schedule": schedule,
    }
