"""Unit tests for the deterministic validation rules."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "sqlite://")  # in-memory for tests

import pytest  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.schemas import ExtractedLineItem  # noqa: E402
from app.seed import seed_catalog  # noqa: E402
from app.validation import validate_and_score_item  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def db():
    init_db()
    with Session(engine) as session:
        seed_catalog(session)


def make_item(**overrides) -> ExtractedLineItem:
    base = dict(
        raw_text="test line",
        product_category="Pipe",
        material_grade="ASTM A106 GRADE B",
        nominal_size='4"',
        schedule_or_rating="SCH 40",
        quantity=10,
    )
    base.update(overrides)
    return ExtractedLineItem(**base)


def score(item: ExtractedLineItem) -> dict:
    with Session(engine) as session:
        return validate_and_score_item(item, session)


def test_clean_item_scores_full_confidence():
    result = score(make_item())
    assert result["confidence"] == 1.0
    assert result["requires_review"] is False
    assert result["flags"] == []


def test_unknown_material_costs_confidence():
    result = score(make_item(material_grade="ASTM A335 GRADE P22"))
    assert result["confidence"] == 0.65
    assert result["requires_review"] is True


def test_invalid_size_schedule_combo():
    result = score(make_item(nominal_size='5"'))
    assert result["confidence"] == 0.60
    assert any("Invalid size/schedule" in f for f in result["flags"])


def test_exotic_alloy_always_flagged():
    result = score(make_item(material_grade="MONEL 400"))
    assert result["confidence"] == 0.85
    assert result["requires_review"] is True


def test_schedule_aliases_normalize():
    result = score(make_item(schedule_or_rating="40"))
    assert result["normalized_schedule"] == "SCH 40"
    assert result["confidence"] == 1.0


def test_missing_quantity_flagged():
    result = score(make_item(quantity=0))
    assert result["requires_review"] is True
