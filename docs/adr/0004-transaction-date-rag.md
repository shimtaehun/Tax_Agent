# ADR 0004 — Transaction-Date-Based Law Retrieval

Date: 2026-05-17
Status: Accepted

## Context

Tax treatment must be reproducible for the transaction date. Current law can differ from the law effective when a receipt was issued.

## Decision

Every law chunk stores `effective_from`, `effective_to`, `content_hash`, and `corpus_version`. Retrieval filters chunks with `effective_from <= as_of_date < effective_to`, where `as_of_date` is the receipt transaction date.

## Consequences

- Old decisions can be reproduced.
- Corpus updates append/version chunks instead of overwriting meaning.
- Tests can prove that different transaction dates return different legal context.
