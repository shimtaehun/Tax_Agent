# AGENTS.md

Tax-Copilot repository instructions for Codex.

## Operating Mode

- Keep changes small and phase-scoped.
- Prefer existing design in `docs/MASTER_DESIGN_DOCUMENT.md`.
- Do not read the full master document unless necessary. Use `rg` and read only relevant sections.
- Ask before irreversible architecture, security, or data-loss decisions.
- Make reasonable implementation choices for small details.

## Project Facts

- Project: Tax-Copilot
- Python package: `tax_copilot`
- Backend layout: `backend/src/tax_copilot/`
- Main design doc: `docs/MASTER_DESIGN_DOCUMENT.md`
- Learning notes: `docs/LEARNING_NOTES/`
- ADRs: `docs/DECISIONS.md`

## Hard Rules

- LLM must not perform tax calculations. Use deterministic Python tools with `Decimal` or integer basis points.
- Law retrieval must use transaction date, not current date.
- No legal basis means `requires_human_review=True`.
- Do not store image/PDF bytes in LangGraph state. Store paths only.
- `human_review_node` must only call `interrupt()` and must not call LLM, DB, or external APIs.
- Scope all user, receipt, and judgment queries by `tenant_id`.
- Record all status transitions in `audit_events`.
- Reassign SQLAlchemy JSON dicts instead of mutating nested values in place.
- Never hardcode secrets.
- Do not put unverified KPI/RAGAS numbers in README.

## Current Stack

- Python 3.11, FastAPI, SQLAlchemy 2.x async, Alembic
- LangGraph, Pydantic v2, Gemini 2.5 Flash
- Gemini Embedding 2 with `output_dimensionality=768`
- Qdrant, PostgreSQL, Redis, Celery
- Next.js App Router with polling first

## Verification

- Run targeted tests first.
- Run full test/lint only at phase or PR completion.
- If a command fails because dependencies are missing or external services are unavailable, report the blocker and suggest the smallest next command.
