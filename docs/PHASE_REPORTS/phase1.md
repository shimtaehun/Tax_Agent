# Phase 1 Report

Date: 2026-05-24

## Goal

Implement tenant-scoped authentication, file upload with validation, and audit logging
so that a logged-in user can upload a receipt and have it persisted to the database.

## Changed

- Added DB models: `Tenant`, `ClientCompany`, `User`, `Receipt`, `AuditEvent`
  - `ClientCompany` added after design review — receipts must be associated with a
    client company, not just a tenant
  - `Receipt.client_company_id` is NOT NULL
- Added Alembic migration `0001_initial_core_schema.py` (5 tables, indices, constraints)
- Added `auth/password.py` using `bcrypt` directly (passlib incompatible with bcrypt 4.x + Python 3.12)
- Added `auth/jwt.py` (HS256, 8h expiry, tenant_id + role in payload)
- Added `auth/permissions.py` (`require_admin`, `require_staff_or_admin`)
- Added `api/deps.py` — `get_current_user` injects `CurrentUser` dataclass from Bearer token
- Added `api/v1/auth.py` — `POST /api/v1/auth/login`
- Added `api/v1/receipts.py` — `POST /api/v1/receipts` (upload), `GET /api/v1/receipts/{id}`
- Added `core/receipts/validation.py` — magic bytes, extension↔MIME match, size check, SHA-256 hash
- Added `infra/storage/local.py` — local file storage adapter
- Added `audit/events.py` — `record_event()` writes to `audit_events` table
- Added `schemas/receipts.py` — Pydantic response schemas
- Added `scripts/seed_admin.py` — creates initial tenant + default client company + admin user
- Added ADR 0001 (pip-tools) and ADR 0002 (hexagonal architecture)
- Replaced `passlib[bcrypt]` with `bcrypt` in `requirements/base.in`
- Added `email-validator` to `requirements/base.in`

## Test results

26 tests passing (unit only — no DB required):
- `test_validation.py`: 9 tests — file size, magic bytes, extension mismatch, hash
- `test_auth.py`: 17 tests — bcrypt round-trip, JWT round-trip, tamper detection, permissions
- `test_healthz.py`: 1 test

## Key decisions

**Why `bcrypt` directly instead of `passlib`?**
`passlib`'s `detect_wrap_bug` sends a 72-byte test string to `bcrypt 4.x`, which now
raises `ValueError`. Using `bcrypt` directly avoids this compatibility issue.

**Why NOT NULL on `client_company_id`?**
Every receipt in a tax office belongs to a specific client company. Allowing NULL would
make it impossible to generate per-client reports or export data for a specific client.

**Why magic bytes AND extension check?**
Magic bytes alone allow uploading a `.pdf` with JPEG content (content-type spoofing).
Comparing extension → expected MIME against detected MIME rejects mismatches at the boundary.
