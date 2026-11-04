"""Routing test for the extractor: with an API key configured, extract()
must go down the LLM path (this is the branch a missing function once
broke silently, because the no-key path never touches it)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import extraction  # noqa: E402
from app.config import settings  # noqa: E402
from app.schemas import ExtractedLineItem, RFQExtractionResult  # noqa: E402


def test_extract_routes_to_llm_when_key_set(monkeypatch):
    canned = RFQExtractionResult(line_items=[
        ExtractedLineItem(raw_text="x", product_category="Pipe",
                          material_grade="ASTM A106 GRADE B", nominal_size='4"',
                          schedule_or_rating="SCH 40", quantity=1)
    ])
    monkeypatch.setattr(extraction, "extract_with_llm", lambda text: (canned, "gemini"))
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    result, name = extraction.extract("anything")
    assert name == "llm-gemini"
    assert result.line_items[0].quantity == 1


def test_extract_uses_rules_without_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "google_api_key", None)
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    monkeypatch.setattr(settings, "openai_api_key", None)
    result, name = extraction.extract('10 pcs 4" SCH 40 A106 Gr B pipe')
    assert name == "rules-fallback"
    assert len(result.line_items) == 1


def test_extract_degrades_to_rules_when_llm_fails(monkeypatch):
    def boom(text):
        raise RuntimeError("quota exhausted")

    monkeypatch.setattr(extraction, "extract_with_llm", boom)
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    result, name = extraction.extract('10 pcs 4" SCH 40 A106 Gr B pipe')
    assert name == "rules-fallback"
    assert len(result.line_items) == 1
