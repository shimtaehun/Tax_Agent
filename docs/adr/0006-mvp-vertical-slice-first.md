# 0006. Build the MVP Vertical Slice First

Date: 2026-05-24

## Status

Accepted

## Context

The original 5-week plan included authentication, uploads, storage, Celery, LangGraph, HITL, RAG, Vision, UI, and deployment in the MVP path. That is a strong portfolio target, but implementing all external integrations at once increases schedule risk and makes debugging harder.

The project needs to demonstrate the core product idea first: receipt upload, AI-assisted judgment candidate creation, human review, and audit logging.

## Decision

Implement a mock-backed vertical slice before integrating external services.

The first complete path is:

```text
receipt upload
-> local storage
-> mocked Vision extraction
-> mocked or in-memory RAG retrieval
-> deterministic calculation
-> judgment candidate save
-> HITL review
-> audit log
```

After this path passes integration tests, replace mocks with Gemini Vision, sample law corpus embeddings, Qdrant, Celery, Redis lock, and R2 one at a time.

## Consequences

- The project can show a working product flow earlier.
- External service failures are isolated to adapter integration phases.
- R2, Qdrant, and Celery remain part of the portfolio, but they no longer block the first end-to-end demo.
- README and demo must describe the early corpus as a sample corpus, not as evidence of tax judgment accuracy.
