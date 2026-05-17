# AGENTS.md

Tax-Copilot repository instructions for Codex.

## Operating Mode

- Keep changes small and phase-scoped.
- Start design sync by reading `docs/DESIGN_INDEX.md` first.
- Do not read all split design documents at once. Use the routing table in `DESIGN_INDEX.md` and `rg` to open only the relevant module or section.
- Ask before irreversible architecture, security, data-loss, or ADR-level design decisions.
- Make reasonable implementation choices for small details based on existing code and the design docs.
- If a design decision changes, update the relevant `docs/DESIGN_*.md` module and the related summary/routing line in `docs/DESIGN_INDEX.md`.
- Record major decisions as ADRs under `docs/adr/`.

## Design Documents

The old single master design document has been split for token control. Treat `DESIGN_INDEX.md` as the entry point.

| File | Purpose |
| --- | --- |
| `docs/DESIGN_INDEX.md` | Compact summary and module routing. Load this first in new design-related work. |
| `docs/DESIGN_CORE.md` | Project identity, principles, legal positioning, MVP scope, tech decisions, architecture, folder structure, domain model. |
| `docs/DESIGN_AGENT.md` | LangGraph, HITL, RAG, law corpus/versioning, receipt file handling, Vision, Celery. |
| `docs/DESIGN_OPS.md` | DB schema, auth, security, logging, errors, graceful degradation, tests, deployment, cost, API versioning. |
| `docs/DESIGN_PLAN.md` | Roadmap, 5-week plan, backlog, pitfalls, portfolio/demo materials, README structure. |
| `docs/CLAUDE.md` | Claude-specific collaboration guide. Use only as reference when explicitly relevant. |

## Module Routing

| Work type | Read |
| --- | --- |
| New session or quick project sync | `docs/DESIGN_INDEX.md` only |
| Domain model, MVP scope, tech decision changes | `docs/DESIGN_INDEX.md` + `docs/DESIGN_CORE.md` |
| LangGraph nodes, HITL, RAG, Vision, Celery tasks | `docs/DESIGN_INDEX.md` + `docs/DESIGN_AGENT.md` |
| DB schema, auth, logging, security, deployment | `docs/DESIGN_INDEX.md` + `docs/DESIGN_OPS.md` |
| Schedule changes, ADRs, README, portfolio material | `docs/DESIGN_INDEX.md` + `docs/DESIGN_PLAN.md` |
| Cross-cutting domain and agent changes | `docs/DESIGN_INDEX.md` + `docs/DESIGN_CORE.md` + `docs/DESIGN_AGENT.md` |

## Project Facts

- Project: Tax-Copilot
- Python package: `tax_copilot`
- Backend layout: `src/tax_copilot/`
- Design entry point: `docs/DESIGN_INDEX.md`
- Learning notes: `docs/LEARNING_NOTES/`
- ADRs: `docs/adr/`
- Frontend: `frontend/` (Next.js App Router, Week 5 focus)

## Hard Rules

- LLM must not perform tax calculations. Use deterministic Python tools with `Decimal` or integer basis points.
- Law retrieval must use transaction date (`as_of_date`), not current date.
- No legal basis means `requires_human_review=True`.
- Do not store image/PDF bytes in LangGraph state. Store paths only.
- `human_review_node` must only call `interrupt()` and must not call LLM, DB, or external APIs.
- Scope all user, receipt, and judgment queries by `tenant_id`.
- Record all status transitions in `audit_events`.
- Reassign SQLAlchemy JSON dicts instead of mutating nested values in place.
- Never hardcode secrets.
- Do not put unverified KPI/RAGAS numbers in README.
- Keep the legal disclaimer visible in README, login, receipt UI, API responses, and audit-log export when those surfaces are implemented.

## Current Stack

- Python 3.11, FastAPI, SQLAlchemy 2.x async, Alembic
- LangGraph, Pydantic v2, Gemini 2.5 Flash
- Gemini Embedding 2 with `output_dimensionality=768`, `gemini-embedding-001` fallback
- Qdrant, PostgreSQL, Redis, Celery
- Next.js App Router with polling first
- pip + pip-tools under `requirements/`; do not switch to uv or Poetry without an ADR

## Code Boundaries

- `core/` is pure domain code. Do not import DB, Redis, Gemini, Qdrant, FastAPI, or environment-driven adapters there.
- External systems belong in `infra/`; API and worker orchestration should depend inward.
- Prefer files under 400 lines, functions under 50 lines, and at most 5 parameters unless an existing pattern says otherwise.
- Use Google-style docstrings in English. Keep domain-explaining inline comments short and useful.

## Verification

- Run targeted tests first.
- Run full test/lint only at phase or PR completion.
- If a command fails because dependencies are missing or external services are unavailable, report the blocker and suggest the smallest next command.
- Do not add broad new dependencies or services just to satisfy a narrow task.
