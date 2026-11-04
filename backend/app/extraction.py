"""Extraction: turn raw RFQ text into structured line items.

Primary path is an LLM with structured output (Pydantic schema) — Claude if
ANTHROPIC_API_KEY is set, else OpenAI. When no key is configured we fall
back to a local rules-based parser. The fallback is deliberately simple:
it covers the phrasing we see over and over on real RFQs and lets the
pipeline, UI, and eval harness run offline. The eval numbers in the README
are from the fallback; they improve noticeably with a live model.
"""
import re
import time

from .config import settings
from .schemas import ExtractedLineItem, RFQExtractionResult

SYSTEM_PROMPT = """You extract structured line items from industrial RFQ emails \
for a pipe/valve/fitting distributor. Extract every line item the customer is \
asking to quote. Normalize material grades to their catalog form where you can \
(e.g. "A106 Gr B" -> "ASTM A106 GRADE B", "316L" pipe -> "ASTM A312 TP316L"). \
Keep nominal sizes in the form 4", 2-1/2". Schedules look like SCH 40 / STD / XS; \
valve and flange ratings look like 150#, 300#, 3000#. Do not invent items that \
are not in the text. If the sender's company is identifiable, set customer_name."""


# Free-tier models get overloaded or quota-capped one at a time; trying a
# short chain keeps a submission from depending on a single model's mood.
GEMINI_MODEL_CHAIN = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-2.0-flash"]


def _build_llm(model: str | None = None):
    """Returns (llm, provider_name). Gemini first: its free tier is enough
    for this workload, so it's the default when a key is provided."""
    if settings.effective_gemini_key:
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=model or settings.gemini_model,
            google_api_key=settings.effective_gemini_key,
            temperature=0,
            # One attempt, bounded: the model chain in extract_with_llm is
            # the retry strategy. SDK-level retries on top of it multiplied
            # submission latency when the free tier was overloaded (a
            # failing chain of 3 models x retries took tens of seconds
            # before the rules fallback ever ran).
            max_retries=0,
            timeout=8,
        )
        return llm, "gemini"
    if settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(
            model=settings.extraction_model,
            api_key=settings.anthropic_api_key,
            temperature=0,
        )
        return llm, "claude"
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o-mini", api_key=settings.openai_api_key, temperature=0)
    return llm, "openai"


def extract_with_llm(raw_text: str) -> tuple[RFQExtractionResult, str]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": raw_text},
    ]
    if settings.effective_gemini_key:
        models = [settings.gemini_model] + [
            m for m in GEMINI_MODEL_CHAIN if m != settings.gemini_model
        ]
        last_exc: Exception | None = None
        started = time.monotonic()
        for model in models:
            # Overall budget for the whole chain: if the provider is
            # having a bad day, degrade to the rules parser within a
            # bounded time instead of serially burning 8s per model.
            if last_exc is not None and time.monotonic() - started > 12:
                break
            llm, _ = _build_llm(model)
            try:
                result = llm.with_structured_output(RFQExtractionResult).invoke(messages)
                return result, "gemini"
            except Exception as exc:  # noqa: BLE001 - try the next model
                print(f"Gemini model {model} failed: {exc}")
                last_exc = exc
        raise last_exc or RuntimeError("no Gemini model available")
    llm, provider = _build_llm()
    result = llm.with_structured_output(RFQExtractionResult).invoke(messages)
    return result, provider


# --- Offline fallback parser ------------------------------------------------

_MATERIAL_PATTERNS = [
    (r"MONEL\s*400", "MONEL 400"),
    (r"INCONEL\s*625", "INCONEL 625"),
    (r"INCONEL\s*600", "INCONEL 600"),
    (r"HASTELLOY\s*C[-\s]?276", "HASTELLOY C276"),
    (r"(?:DUPLEX|UNS\s*S32205)\s*2205|2205\s*DUPLEX", "DUPLEX 2205"),
    (r"A106\s*(?:GR\.?|GRADE)?\s*B", "ASTM A106 GRADE B"),
    (r"A53\s*(?:GR\.?|GRADE)?\s*B", "ASTM A53 GRADE B"),
    (r"A106\b", "ASTM A106 GRADE B"),
    (r"A312\s*TP\s*316L|TP\s*316L", "ASTM A312 TP316L"),
    (r"A312\s*TP\s*316|TP\s*316\b", "ASTM A312 TP316"),
    (r"A312\s*TP\s*304|TP\s*304\b", "ASTM A312 TP304"),
    (r"316L", "STAINLESS 316L"),
    (r"316\s*(?:SS|STAINLESS)", "STAINLESS 316"),
    (r"304\s*(?:SS|STAINLESS)", "STAINLESS 304"),
    (r"A234\s*WPB", "ASTM A234 WPB"),
    (r"A105", "ASTM A105"),
    (r"A350\s*LF2", "ASTM A350 LF2"),
    (r"API\s*5L", "API 5L GRADE B"),
]

_CATEGORY_PATTERNS = [
    (r"\bPIPE\b", "Pipe"),
    (r"\bTUBE\b|\bTUBING\b", "Tube"),
    (r"\bELBOW\b|\bELL\b", "Fitting"),
    (r"\bTEE\b", "Fitting"),
    (r"\bREDUCER\b", "Fitting"),
    (r"\bCAP\b", "Fitting"),
    (r"\bCOUPLING\b", "Fitting"),
    (r"\bUNION\b", "Fitting"),
    (r"\bNIPPLE\b", "Fitting"),
    (r"\bFITTING", "Fitting"),
    (r"\bFLANGE\b|\bFLG\b", "Flange"),
    (r"\bVALVE\b|\bGATE\b|\bGLOBE\b|\bBALL\b|\bCHECK\b|\bBUTTERFLY\b", "Valve"),
    (r"\bSTUD\s*BOLT|\bBOLT", "Stud Bolt"),
    (r"\bGASKET\b", "Gasket"),
]

_SIZE_RE = re.compile(r'(\d+(?:-\d+/\d+|\.\d+|/\d+)?)\s*(?:"|″|\bIN\b|\bINCH)', re.IGNORECASE)
_SCHEDULE_RE = re.compile(
    r"\bSCH\s*(40|80|160|120|10|30)S?\b|\bS/(40|80)\b|\b(STD|STANDARD|XS|XH)\b", re.IGNORECASE
)
_RATING_RE = re.compile(r"\b(150|300|600|900|1500|2500|2000|3000|6000)\s*#")
_QTY_PATTERNS = [
    re.compile(r"\bQTY[:\s]*(\d+)", re.IGNORECASE),
    re.compile(r"\b(\d+)\s*(?:PCS|PC|EA|EACH|SETS|FT|FEET|LGT|LENGTHS|JTS|JOINTS)\b", re.IGNORECASE),
    re.compile(r"^\s*\d+\s+(\d+)\s+\d"),
    re.compile(r"^\s*(\d+)\s*[xX]\b"),
    re.compile(r"[xX]\s*(\d+)\s*$"),
]
_UOM_RE = re.compile(r"\b(FT|FEET|LGT|LENGTHS|JTS|JOINTS)\b", re.IGNORECASE)

_SKIP_LINE = re.compile(
    r"^(hi|hello|thanks|thank you|regards|best|please|we need|we are|subject|from|to|date|"
    r"rfq|quote request|request for|dear|good (morning|afternoon)|let me know|need pricing|"
    r"pricing on|delivery|ship to|payment|terms|call me|sent from|--+$)",
    re.IGNORECASE,
)


def _parse_line(line: str) -> ExtractedLineItem | None:
    upper = line.upper()
    size_m = _SIZE_RE.search(line)
    cat = next((name for pat, name in _CATEGORY_PATTERNS if re.search(pat, upper)), None)
    if not size_m and not cat:
        return None
    if not size_m and cat and not re.search(r"\d", line):
        return None  # prose mentioning a product, not a line item

    material = next((g for pat, g in _MATERIAL_PATTERNS if re.search(pat, upper)), "")
    schedule = None
    sched_m = _SCHEDULE_RE.search(upper)
    if sched_m:
        schedule = next(g for g in sched_m.groups() if g)
        schedule = {"40": "SCH 40", "80": "SCH 80", "160": "SCH 160", "120": "SCH 120",
                    "10": "SCH 10", "30": "SCH 30"}.get(schedule, schedule)
    else:
        rating_m = _RATING_RE.search(upper)
        if rating_m:
            schedule = f"{rating_m.group(1)}#"

    quantity = 0
    for pat in _QTY_PATTERNS:
        qm = pat.search(line)
        if qm:
            quantity = int(qm.group(1))
            break

    uom = "EA"
    uom_m = _UOM_RE.search(upper)
    if uom_m:
        uom = "FT" if uom_m.group(1) in ("FT", "FEET") else "LGT"

    size = size_m.group(1) + '"' if size_m else ""
    return ExtractedLineItem(
        raw_text=line,
        product_category=cat or "Pipe",
        material_grade=material,
        nominal_size=size,
        schedule_or_rating=schedule,
        quantity=quantity,
        unit_of_measure=uom,
    )


def extract_with_rules(raw_text: str) -> RFQExtractionResult:
    customer = None
    from_m = re.search(r"^From:\s*(.+)$", raw_text, re.MULTILINE)
    if from_m:
        customer = from_m.group(1).strip()

    items = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip(" \t•-*")
        if len(line) < 6:
            continue
        # Prose openers ("We need...", "Please quote") are skipped only when
        # the line carries no size spec of its own - a sentence like
        # "We need 500 ft of 6 inch STD pipe" is a line item, not a greeting.
        if _SKIP_LINE.match(line) and not _SIZE_RE.search(line):
            continue
        parsed = _parse_line(line)
        if parsed:
            items.append(parsed)
    return RFQExtractionResult(customer_name=customer, line_items=items)


def extract(raw_text: str) -> tuple[RFQExtractionResult, str]:
    """Returns (result, extractor_name).

    If the LLM call fails (quota, overload, bad key), we degrade to the
    rules parser instead of failing the submission outright - an RFQ in
    the queue with a note beats a 500 to the sales rep.
    """
    if settings.effective_gemini_key or settings.anthropic_api_key or settings.openai_api_key:
        try:
            result, provider = extract_with_llm(raw_text)
            return result, f"llm-{provider}"
        except Exception as exc:  # noqa: BLE001 - deliberate degrade, see docstring
            print(f"LLM extraction failed, falling back to rules parser: {exc}")
    return extract_with_rules(raw_text), "rules-fallback"
