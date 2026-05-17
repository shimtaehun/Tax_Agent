# ADR 0002 — 헥사고날 아키텍처 (core/infra 분리)

Date: 2026-05-17
Status: Accepted

## Context

FastAPI + SQLAlchemy 프로젝트에서 도메인 로직과 외부 시스템을 어떻게 분리할지 결정해야 한다.

## Decision

헥사고날 아키텍처를 적용한다.
- `src/tax_copilot/core/` — 순수 도메인. 표준 라이브러리 + pydantic만 허용.
- `src/tax_copilot/infra/` — DB, Qdrant, Gemini, R2 어댑터.
- `src/tax_copilot/api/` — FastAPI 라우터.
- `src/tax_copilot/workers/` — Celery 태스크.
의존성 방향: api/workers → infra → core. core는 외부를 모른다.

## Consequences

- DB 교체, AI 모델 교체 시 infra만 수정
- core 단독 단위 테스트 가능 (외부 시스템 불필요)
- 상세는 git history 참조
