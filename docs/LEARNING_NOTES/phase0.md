# Phase 0 학습 노트

## Step 0.1 — Repo 초기화, 폴더 구조, .gitignore

새로 배운 것:
- src layout은 `pip install -e .` 없이는 임포트가 안 되어 로컬/배포 환경을 일치시킨다
- core/infra 분리: core는 외부를 모르므로 DB 교체·모델 교체 시 core 코드 무수정

면접 질문: "왜 src layout을 쓰셨나요?"

---

## Step 0.2 — requirements/ + pip-tools

새로 배운 것:
- `.in`은 "내가 직접 선언한 것", `.txt`는 pip-compile이 resolve한 전체 트리
- 패키지 업그레이드: `.in` 수정 후 `pip-compile --upgrade` 재실행
- base.in / dev.in 분리로 프로덕션에는 dev 도구가 들어가지 않음

면접 질문: "pip freeze 대신 pip-tools를 쓴 이유는?"

---

## Step 0.3 — pyproject.toml + ruff + mypy + pre-commit

새로 배운 것:
- ruff는 flake8 + isort + 여러 lint 규칙을 하나로 통합. 속도가 극단적으로 빠름
- mypy strict는 core/에만 적용. 외부 라이브러리 stubs 없으면 ignore_missing_imports
- detect-secrets: 실제 시크릿이 아닌 예시 값도 탐지 → `# pragma: allowlist secret`으로 제외

면접 질문: "코드 품질을 어떻게 관리했나요?"

---

## Step 0.4 — Docker Compose

새로 배운 것:
- healthcheck로 서비스 준비 상태를 확인 후 의존 서비스 시작
- named volume으로 컨테이너 재시작 시 데이터 보존
- `.env.example`을 git 추적, `.env`는 gitignore

면접 질문: "로컬 개발 환경을 어떻게 구성했나요?"

---

## Step 0.5 — FastAPI + pydantic-settings

새로 배운 것:
- `lifespan` 컨텍스트 매니저로 startup/shutdown 처리 (deprecated `on_event` 대신)
- `BaseSettings`는 `.env` 파일 → 환경변수 순으로 값을 읽음
- middleware에서 `request_id_var.set()` 후 `reset()`으로 contextvar 누수 방지

면접 질문: "FastAPI에서 의존성 주입과 설정 관리를 어떻게 했나요?"

---

## Step 0.6 — SQLAlchemy 2.0 async + Alembic

새로 배운 것:
- `AsyncSession`은 `await session.execute()`로 쿼리. 2.0 style은 `select()` + `scalars()`
- Alembic `env.py`에서 `target_metadata = Base.metadata` 설정해야 autogenerate 동작
- `pool_pre_ping=True`: 연결이 끊어진 경우 자동 재연결

면접 질문: "DB 마이그레이션을 어떻게 관리했나요?"

---

## Step 0.7 — structlog

새로 배운 것:
- structlog는 JSON으로 출력해 로그 수집 시스템(Datadog, CloudWatch 등)과 연동 용이
- `ContextVar`로 request_id를 스레드 안전하게 전파
- PII 마스킹을 logging pipeline에 processor로 삽입 → 코드 전역에 마스킹 보장

면접 질문: "로깅 전략과 PII 보호를 어떻게 구현했나요?"

---

## Step 0.8 — GitHub Actions CI

새로 배운 것:
- `services` 블록으로 PostgreSQL/Redis를 CI 환경에 띄움
- `cache: pip` + `cache-dependency-path`로 의존성 캐시
- `ASGITransport`로 실제 서버 없이 FastAPI 앱 테스트

면접 질문: "CI 파이프라인을 어떻게 구성했나요?"
