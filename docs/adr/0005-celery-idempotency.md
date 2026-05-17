# ADR 0005 — Celery with Idempotent Receipt Tasks

Date: 2026-05-17
Status: Accepted

## Context

Receipt processing can involve OCR, RAG, HITL checkpointing, and retries. FastAPI background tasks are not durable enough for this work.

## Decision

Use Celery with Redis broker/lock. Configure late acknowledgment and deterministic task ids based on tenant, receipt hash, and attempt number. User-facing status is read from the database, not Celery result state.

## Consequences

- Worker crashes can be retried without duplicate processing.
- Redis lock TTL must be chosen conservatively.
- DB status transitions remain the primary audit and polling surface.
