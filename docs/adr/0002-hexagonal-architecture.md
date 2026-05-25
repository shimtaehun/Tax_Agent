# ADR 0002 — Hexagonal architecture (core / infra separation)

Date: 2026-05-24
Status: Accepted

## Context

세무 계산 로직, 도메인 예외, 판단 스키마는 LLM·벡터DB·ORM 같은 외부 시스템과
독립적으로 테스트하고 교체할 수 있어야 한다.

## Decision

```
api/, workers/, agents/   ← 사용 계층
         ↓
infra/                    ← 외부 시스템 어댑터 (SQLAlchemy, Gemini, Qdrant, Redis)
         ↓
core/                     ← 순수 도메인 (표준 라이브러리 + pydantic만 허용)
```

`core/`는 sqlalchemy, google.generativeai, qdrant_client, redis, fastapi를 import하지 않는다.

## Consequences

**Good:**
- 세액 계산, 리스크 판정, 파일 검증을 mock 없이 단위 테스트 가능
- LLM 공급자 교체(Gemini → OpenAI) 시 infra/llm만 수정
- 면접에서 "왜 이 구조인가"에 명확한 답변 가능

**Bad:**
- 작은 기능도 core → infra → api 3계층을 거쳐야 함
- 초기 작업량 증가

포트폴리오 맥락에서 장점이 단점을 상회한다.
