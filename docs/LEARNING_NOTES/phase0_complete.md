# Phase 0 완료 기록

완료일: 2026-05-24
총 작업 내용: repo skeleton 전체 구성 + 품질 도구 설정

---

## 구현된 것

### 폴더 구조 (src layout)
```
src/tax_copilot/
├── api/          # FastAPI 라우터, 에러 핸들러, DI
├── core/         # 순수 도메인 (외부 라이브러리 없음)
├── infra/        # 외부 시스템 어댑터
├── agents/       # LangGraph (Phase 2에서 구현)
├── rag/          # RAG 파이프라인 (Phase 3)
├── workers/      # Celery (Phase 5)
├── auth/         # JWT, 비밀번호, 권한
├── audit/        # 감사 로그
└── schemas/      # Pydantic API 스키마
```

### 설정 완료
- pyproject.toml: ruff (E,F,I,B,UP,S), mypy strict (core only)
- .pre-commit-config.yaml: ruff, mypy, detect-secrets
- Docker Compose: PostgreSQL 16 + Redis 7
- GitHub Actions CI: lint + mypy + pytest
- structlog JSON 로깅 + request_id contextvar + PII 마스킹

### FastAPI skeleton
- `api/main.py`: lifespan, request_id middleware, /healthz
- `api/errors.py`: 도메인 예외 → HTTP 상태 코드 매핑
- `core/exceptions.py`: TaxCopilotError 계층

### SQLAlchemy + Alembic
- `infra/database.py`: async engine + session factory
- `infra/db/models/base.py`: Base + TimestampMixin
- `alembic/env.py`: async migration 지원

### ADR
- `docs/adr/0001-pip-tools.md`
- `docs/adr/0002-hexagonal-architecture.md`

---

## 핵심 학습 포인트

**src layout이 필요한 이유**
`pip install -e .` 없이 import하면 로컬 개발과 배포 환경의 import 경로가 달라질 수 있다.
editable install을 강제함으로써 `src/` 안의 코드가 실제 패키지처럼 동작하게 된다.

**헥사고날 의존성 방향**
`core/`는 외부를 모른다. 이 덕분에 DB나 LLM을 mock하지 않고 도메인 로직만 단위 테스트할 수 있다.

**structlog의 장점**
`logger.info("event", key=value)` 형식으로 로그가 JSON이 되면 운영 환경 로그 수집·검색이 쉬워진다.
PII 마스킹을 processor로 삽입하면 코드 전역에 자동 적용된다.
