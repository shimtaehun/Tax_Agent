# TODOS

Backlog items identified during the "card-company statement Excel import"
architecture review (`/plan-eng-review`). Not required for the first
implementation pass — tracked here so they aren't lost.

## 1. Statement bulk-import API rate limiting / batching

A single statement can contain hundreds of rows. Each row goes through
`tax_law_retrieval` (embedding + vector search), so a naive bulk import could
hit Gemini/embedding API rate limits or spike vector DB load.

- Depends on: statement ingestion pipeline (`core/statements/ingest.py`)
  landing first, so real load can be measured.
- Candidate fixes: batch/queue statement rows through Celery with
  concurrency limits, cache embeddings for repeated law lookups, or
  pre-fetch/cache the relevant law corpus per tax period.

## 2. Frontend UI for ambiguous match candidates (NEEDS_REVIEW)

Introducing confidence tiers in `match_transaction_node` (high-confidence
auto-match vs. ambiguous -> human review) will produce a steady stream of
"is this statement row the same transaction as this receipt?" review items.
There is currently no frontend for this — `frontend/app/page.tsx` and
`frontend/app/history/page.tsx` only support per-receipt review.

- Depends on: `transactions` / `match_transaction_node` backend +
  `/api/v1/transactions...` endpoints.
- Suggested follow-up: `/plan-design-review` once the backend contract
  exists.

## 3. Additional card-company statement parsers

First implementation covers one card company's Excel format
(`core/statements/parsers/<first_company>.py`) under the
`StatementParser` plugin architecture (`base.py` protocol + `registry.py`).
Each additional card company needs its own sample files, parser, and golden
fixture tests.

- Depends on: `core/statements/base.py` (StatementParser protocol),
  `registry.py`, and the first parser landing.
- Each new parser is independent work and can be parallelized once the
  protocol is stable.
