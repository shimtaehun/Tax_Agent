# Phase 0 학습 노트 — 프로젝트 기반 세팅

> 이 파일은 직접 읽으면서 공부하는 용도로 작성되었습니다.
> 코드 위치를 가리키는 `파일:줄번호` 형식으로 직접 열어서 확인해 보세요.

---

## 1. src layout — 왜 `src/` 폴더를 쓰는가?

### 문제 상황

Python 프로젝트를 그냥 만들면 보통 이렇게 됩니다.

```
my_project/
├── my_package/
│   ├── __init__.py
│   └── app.py
└── tests/
    └── test_app.py
```

`tests/test_app.py`에서 `import my_package`를 하면... 작동합니다. 왜냐하면 Python이 현재 폴더(.)를 자동으로 경로에 포함시키기 때문입니다.

### 무엇이 문제인가?

로컬에서는 됩니다. 그런데 배포(Docker, 서버)하면 `my_package`가 제대로 설치되지 않은 상태에서 실행할 수도 있습니다. 로컬과 배포 환경의 동작이 달라집니다.

### src layout이 해결하는 방법

```
my_project/
├── src/
│   └── my_package/     ← 여기로 옮김
│       ├── __init__.py
│       └── app.py
└── tests/
    └── test_app.py
```

이제 `src/`는 자동으로 경로에 포함되지 않습니다. `import my_package`는 **실패**합니다.

반드시 `pip install -e .`로 패키지를 설치해야만 import가 됩니다. 이렇게 하면 로컬 개발 환경과 배포 환경이 완전히 동일한 방식으로 패키지를 찾습니다.

```bash
pip install -e .   # -e는 editable 모드: 코드 수정이 즉시 반영됨
```

### 이 프로젝트에서

```
src/tax_copilot/   ← 실제 패키지
tests/             ← 테스트 (src/ 밖)
```

`pyproject.toml`에 다음 설정이 있어서 pip이 src 안을 찾습니다:
```toml
[tool.setuptools.packages.find]
where = ["src"]
```

**면접 질문**: "src layout을 쓴 이유는?" → "로컬 개발 환경과 배포 환경의 import 경로를 일치시키기 위해서입니다. src layout 없이는 `pip install` 없이도 테스트가 통과하지만, 실제 배포에서 실패할 수 있습니다."

---

## 2. 헥사고날 아키텍처 — 의존성 방향 규칙

### 핵심 개념

코드를 세 층으로 나눕니다:

```
┌─────────────────────────────────────┐
│  api/, agents/, workers/            │  ← 사용 계층 (진입점)
└────────────────┬────────────────────┘
                 ↓ 의존
┌─────────────────────────────────────┐
│  infra/                             │  ← 어댑터 계층 (외부 연결)
└────────────────┬────────────────────┘
                 ↓ 의존
┌─────────────────────────────────────┐
│  core/                              │  ← 도메인 계층 (순수 로직)
└─────────────────────────────────────┘
```

**핵심 규칙**: 화살표 방향이 항상 아래로만 향합니다. `core/`는 `infra/`를 모릅니다. `infra/`는 `api/`를 모릅니다.

### 왜 이렇게 하는가?

`core/`에 SQLAlchemy나 FastAPI import가 없으면:
- DB를 PostgreSQL에서 SQLite로 바꿔도 `core/` 코드를 수정할 필요가 없습니다.
- `core/` 코드를 테스트할 때 DB가 없어도 됩니다.
- LangGraph를 다른 워크플로우 엔진으로 교체해도 도메인 규칙은 그대로입니다.

### 이 프로젝트에서 위반 예시 (하면 안 되는 것)

```python
# src/tax_copilot/core/receipts/validation.py — 이건 OK (표준 라이브러리만 사용)
import hashlib  # OK: 표준 라이브러리

# 이건 금지
from sqlalchemy.orm import Session  # 금지: core에 외부 라이브러리 import
```

**면접 질문**: "헥사고날 아키텍처를 쓴 이유는?" → "도메인 로직(core)이 외부 시스템에 의존하지 않도록 해서, DB나 LLM을 교체할 때 비즈니스 규칙을 건드리지 않아도 됩니다. 또한 core 단위 테스트 시 mock이 필요 없습니다."

---

## 3. pip-tools — 의존성 관리

### 일반 `pip freeze`의 문제

```bash
pip install fastapi
pip freeze > requirements.txt
```

`requirements.txt`에는 내가 원한 `fastapi`뿐 아니라 fastapi가 끌어온 수십 개 패키지가 다 들어갑니다. 어떤 게 내가 직접 선택한 건지, 어떤 게 자동으로 딸려온 건지 구분이 안 됩니다.

### pip-tools 방식

```
requirements/
├── base.in    ← 내가 직접 선택한 패키지만 (사람이 관리)
├── base.txt   ← pip-compile이 생성한 전체 트리 (자동 생성, git 추적)
├── dev.in     ← 개발 도구
└── dev.txt
```

`base.in` 예시:
```
fastapi>=0.110
pydantic>=2.0
```

`pip-compile base.in` 실행 → `base.txt` 자동 생성 (전체 의존성 트리, 버전 고정)

업그레이드 방법:
```bash
pip-compile --upgrade base.in   # 최신 버전으로 재해결
pip-sync base.txt dev.txt       # 실제 환경에 적용
```

**면접 질문**: "pip freeze 대신 pip-tools를 쓴 이유는?" → "내가 직접 선택한 의존성과 자동으로 딸려온 의존성을 구분할 수 있고, 버전이 정확히 고정되어 재현 가능한 빌드가 가능합니다."

---

## 4. ruff — 코드 품질 도구

### ruff가 대체하는 것들

예전에는 이걸 다 따로 설치했습니다:
- `flake8` (lint)
- `isort` (import 순서 정렬)
- `black` (포매팅)
- `pyupgrade` (Python 구문 현대화)
- `bandit` (보안 취약점 탐지)

ruff는 이 모두를 하나로 통합합니다. 속도도 훨씬 빠릅니다 (Rust로 작성).

### 이 프로젝트 설정 (`pyproject.toml`)

```toml
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "S"]
```

- `E`: PEP8 스타일 오류
- `F`: Pyflakes (미사용 import, 정의되지 않은 변수 등)
- `I`: isort (import 정렬)
- `B`: 버그 위험 패턴
- `UP`: pyupgrade (Python 3.10+ 구문으로 현대화)
- `S`: bandit (보안 취약점)

### mypy — 타입 체크

```toml
[tool.mypy]
[[tool.mypy.overrides]]
module = "tax_copilot.core.*"
strict = true          # core만 엄격하게
```

strict 모드는 모든 함수에 타입 어노테이션을 요구하고, `Any` 사용을 제한합니다. `core/`에만 적용하는 이유: 비즈니스 로직에서 타입 오류는 치명적이지만, 설정 파일이나 스크립트는 유연성이 필요합니다.

---

## 5. FastAPI lifespan — 애플리케이션 생명주기

### 예전 방식 (deprecated)

```python
@app.on_event("startup")
async def startup():
    ...

@app.on_event("shutdown")
async def shutdown():
    ...
```

### 현재 방식 (lifespan)

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: yield 전
    db_engine = create_async_engine(settings.database_url)
    app.state.graph = build_graph(checkpointer)

    yield  # ← 여기서 앱이 실행됨

    # shutdown: yield 후
    await db_engine.dispose()

app = FastAPI(lifespan=lifespan)
```

`contextlib.asynccontextmanager` 데코레이터를 쓰면 하나의 함수로 startup과 shutdown을 함께 표현할 수 있습니다.

---

## 6. SQLAlchemy 2.0 async — 비동기 DB 연결

### 핵심 패턴

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@host/db",
    pool_pre_ping=True,   # 끊긴 연결 자동 재연결
)

async def get_db():
    async with AsyncSession(engine) as session:
        yield session

# 쿼리 방법 (2.0 style)
from sqlalchemy import select

async def get_receipt(session: AsyncSession, id: int):
    result = await session.execute(select(Receipt).where(Receipt.id == id))
    return result.scalar_one_or_none()
```

### 왜 `asyncpg`가 필요한가?

PostgreSQL을 비동기로 연결하려면 비동기 드라이버가 필요합니다. `asyncpg`가 그 역할을 합니다. URL에 `+asyncpg`를 붙여서 어떤 드라이버를 쓸지 지정합니다.

```
postgresql+asyncpg://   ← SQLAlchemy용 (ORM)
postgresql://           ← psycopg3용 (LangGraph checkpointer)
```

이 두 URL 형식이 다르기 때문에 `config.py`에서 `checkpointer_url`을 별도로 계산합니다.

---

## 7. structlog — 구조화 로깅

### 일반 로깅의 문제

```python
logging.info(f"Receipt {receipt_id} uploaded by user {user_id}")
```

이 문자열에서 특정 `receipt_id`를 찾으려면 grep이나 정규식이 필요합니다.

### structlog

```python
logger.info("receipt_uploaded", receipt_id=receipt_id, user_id=user_id)
```

출력:
```json
{"event": "receipt_uploaded", "receipt_id": 42, "user_id": 7, "timestamp": "..."}
```

JSON 형태로 나오기 때문에 Datadog, CloudWatch, Loki 같은 로그 수집 시스템에서 바로 필드로 검색할 수 있습니다.

### request_id ContextVar

```python
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
```

`ContextVar`는 스레드(또는 async task)마다 독립적인 값을 가집니다. 미들웨어에서 요청마다 UUID를 설정하면, 그 요청 안의 모든 로그에 자동으로 `request_id`가 붙습니다. 다른 요청의 `request_id`와 섞이지 않습니다.

---

## 8. Alembic — DB 마이그레이션

### 왜 마이그레이션 도구가 필요한가?

DB 스키마를 바꿀 때 (컬럼 추가, 테이블 생성 등) 모든 환경(로컬, 스테이징, 프로덕션)에서 같은 변경을 순서대로 적용해야 합니다. SQL 파일을 직접 관리하면 어디까지 적용했는지 추적하기 어렵습니다.

Alembic은 각 변경을 버전 파일로 관리하고, 어떤 버전까지 적용했는지 DB에 기록합니다.

### 명령어

```bash
# 현재 모델 상태 기준으로 마이그레이션 파일 자동 생성
alembic revision --autogenerate -m "add receipts table"

# 최신 버전으로 적용
alembic upgrade head

# 한 버전 되돌리기
alembic downgrade -1
```

### 이 프로젝트 설정

`alembic/env.py`에서:
```python
from tax_copilot.infra.db.models import Base
target_metadata = Base.metadata
```

`Base.metadata`를 등록해야 autogenerate가 모델 변경을 감지합니다.

---

## 핵심 질문 목록 (면접 준비)

1. "src layout을 쓴 이유는?"
2. "헥사고날 아키텍처에서 core/가 외부 라이브러리를 import하면 안 되는 이유는?"
3. "pip-tools와 pip freeze의 차이는?"
4. "ruff가 하는 일은?"
5. "lifespan 컨텍스트 매니저를 쓰는 이유는?"
6. "asyncpg vs psycopg3 차이는?"
7. "ContextVar를 쓰는 이유는?"
8. "Alembic autogenerate는 어떻게 작동하는가?"
