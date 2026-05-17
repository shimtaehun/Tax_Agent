# ADR 0003 — LangGraph for HITL Workflow

Date: 2026-05-17
Status: Accepted

## Context

Receipt processing must pause for professional review when evidence, business purpose, or legal basis is uncertain. A plain function chain cannot persist state and resume cleanly after external human input.

## Decision

Use LangGraph for the workflow. Split review into:

- `audit_prepare_node`: prepares draft decision and evidence.
- `human_review_node`: only calls `interrupt()`.
- `save_result_node`: saves the resumed final decision.

## Consequences

- Interrupt/resume is explicit and testable.
- Checkpointer lifecycle must be managed by API/worker lifespan.
- Nodes before interrupt must avoid non-idempotent side effects.
