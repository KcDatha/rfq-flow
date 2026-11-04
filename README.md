# RFQ-Flow

**Live demo:** https://rfq-flow.vercel.app — deployed as a single Vercel
project (the FastAPI app serves the built frontend; demo data lives in a
per-instance SQLite file, so it can reset when an instance recycles).
Redeploy with `vercel deploy --prod` from this directory.

Parses the RFQ emails that show up as unstructured text — "20 pcs 4" SCH 40
A106 Gr B pipe, need it Friday" — into structured, validated line items a
sales rep can actually quote from.

The idea is simple: let the LLM do the reading, but never let it do the
judging. Extraction is probabilistic; validation is plain SQL and rules
against the pipe schedule / material catalog, so a confidence score means
the same thing every time it's computed.

## How it works

```
raw email / PDF
      |
      v
 [ extract ]   LangGraph node. Claude/GPT with structured output (Pydantic)
      |        when an API key is configured; otherwise a local rules-based
      |        parser so the whole thing still runs offline.
      v
 [ validate ]  Deterministic checks, no LLM:
      |          - material grade exists in the catalog?        (-0.35)
      |          - size/schedule combo exists in ASME B36.10?   (-0.40)
      |          - exotic alloy (Monel, Inconel, duplex)?       (-0.15)
      |          - quantity missing?                            (-0.20)
      v
 [ route ]     All clean -> AUTO_APPROVED.
               Anything flagged -> HUMAN_REVIEW queue, where a rep can
               correct the fields (the item re-validates on save) and
               approve it. Quoting is one click from there.
```

## Running it

Backend (Python 3.11+):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload   # http://localhost:8000/docs
```

It defaults to a local SQLite file so there's nothing to set up. For
Postgres: `docker compose up -d` and set `DATABASE_URL` (see `.env.example`).

Frontend:

```bash
cd frontend && npm install && npm run dev    # http://localhost:5173
```

Three tabs: submit an RFQ (paste text or upload a PDF — the sample RFQ
button is the fastest way to see it work), browse submissions, and work
the human review queue.

To use a real model for extraction, set one of `GEMINI_API_KEY`,
`ANTHROPIC_API_KEY`, or `OPENAI_API_KEY` in `backend/.env` (or in the
Vercel project settings). Gemini is checked first — a free AI Studio key
is enough for this workload. Without any key you get the fallback
parser — decent on standard phrasing, visibly weaker on weird ones, which
is exactly what the evals are for.

## Evals

`evals/golden_rfqs.json` holds 25 hand-written RFQs with ground-truth line
items, including the nasty cases: a 5" pipe that doesn't exist, SCH 120 on
12", an alloy we don't stock, exotics, and one email with no line items at
all. Run them before touching a prompt, the parser, or the model:

```bash
python -m pytest evals/ -s
```

Current numbers, fallback parser, no API key:

| metric | score |
|---|---|
| material accuracy | 96.1% |
| size accuracy | 100% |
| schedule accuracy | 100% |
| quantity accuracy | 100% |
| hallucination rate | 0% |
| safety fallthrough (invalid spec auto-approved) | 0% |

The two material misses are both ASTM A335 P22, a grade that isn't in the
catalog yet — the validator still flags them for review, which is the
behavior that matters. The suite is wired so a Braintrust logger can be
dropped in later; for now pytest prints the summary.

Backend unit tests for the validation rules live in `backend/tests/`.

## Layout

```
backend/app/
  graph.py        the LangGraph pipeline (extract -> validate -> route)
  extraction.py   LLM structured output + offline fallback parser
  validation.py   deterministic checks + confidence scoring
  models.py       catalog + RFQ tables (SQLModel)
  seed.py         ASME B36.10 pipe schedules, material grades
  pricing.py      starter price book for quote generation
  main.py         FastAPI endpoints
evals/            golden dataset + regression suite
frontend/         React + TypeScript + Tailwind dashboard
```

## Known gaps / next up

- Quote prices come from a small placeholder price book in `pricing.py`.
  Real pricing has to come from the ERP.
- Scanned PDF RFQs need OCR before the text path works on them; typed PDFs
  are fine.
- The fallback parser reads line-by-line, so two items crammed into one
  sentence get merged. The LLM path doesn't have this problem.
- Catalog covers common carbon/stainless/alloy grades and NPS 1/2–24 in
  the usual schedules. Adding a grade is one row in `seed.py`.
