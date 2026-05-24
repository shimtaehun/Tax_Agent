# 의미 기반 중복 영수증 감지 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 같은 영수증을 재촬영해 재업로드한 경우(파일 해시 다름)를 가맹점명 유사도 + 금액 일치로 탐지하고, `Receipt.duplicate_suspect` 필드에 저장해 API 응답에 포함한다.

**Architecture:** `intake_node` 직후 `duplicate_check_node`를 삽입한다. 이 노드는 `parsed_receipt`에서 가맹점명·금액을 읽어 DB를 조회하고, Python-side `rapidfuzz.fuzz.ratio >= 80` 기준으로 의심 중복을 탐지한다. 결과는 `AgentState`를 통해 Celery task로 전달되어 `Receipt` 테이블에 저장된다. HITL 강제 없음.

**Tech Stack:** Python 3.11, rapidfuzz, FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, pytest-asyncio

---

## 파일 구조 (변경 대상)

| 파일 | 변경 종류 | 역할 |
|------|-----------|------|
| `requirements/base.in` | 수정 | `rapidfuzz` 추가 |
| `src/tax_copilot/agents/state.py` | 수정 | `duplicate_suspect`, `duplicate_receipt_ids` 필드 추가 |
| `src/tax_copilot/agents/nodes/duplicate_check.py` | 신규 | 중복 탐지 노드 |
| `src/tax_copilot/agents/graph.py` | 수정 | 노드 등록 + 엣지 수정 |
| `src/tax_copilot/infra/db/models/receipt.py` | 수정 | `duplicate_suspect`, `duplicate_receipt_ids` 컬럼 추가 |
| `alembic/versions/0003_add_duplicate_suspect.py` | 신규 | DB 마이그레이션 |
| `src/tax_copilot/workers/tasks/receipts.py` | 수정 | duplicate 필드 DB 저장 |
| `src/tax_copilot/schemas/receipts.py` | 수정 | API 응답에 필드 추가 |
| `src/tax_copilot/api/v1/receipts.py` | 수정 | `_to_status_response` 수정 |
| `tests/test_vision.py` | 수정 | `TestDuplicateCheckNode` 클래스 추가 |

---

## Task 1: `rapidfuzz` 의존성 + `AgentState` 필드 추가

**Files:**
- Modify: `requirements/base.in`
- Modify: `src/tax_copilot/agents/state.py`
- Test: `tests/test_vision.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_vision.py` `TestTaxDecisionAccountCode` 클래스 바로 아래에 추가

```python
class TestAgentStateDuplicateFields:
    def test_state_has_duplicate_suspect_field(self) -> None:
        from tax_copilot.agents.state import AgentState
        state = AgentState(
            tenant_id=1, receipt_id=1, file_path="/tmp/t.jpg",  # noqa: S108
            file_hash="abc", attempt_number=1,
            transaction_date=None, law_as_of_date=None,
            law_corpus_version="v1", image_quality=None,
            parsed_receipt=None, retrieval_query=None,
            relevant_laws=[], calculation_result=None,
            draft_decision=None, final_decision=None,
            requires_human=False, error_message=None, messages=[],
            duplicate_suspect=True,
            duplicate_receipt_ids=[42, 99],
        )
        assert state["duplicate_suspect"] is True
        assert state["duplicate_receipt_ids"] == [42, 99]
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
DEBUG=true python3 -m pytest tests/test_vision.py::TestAgentStateDuplicateFields -v
```
Expected: `FAILED` — `duplicate_suspect` not in AgentState

- [ ] **Step 3: `requirements/base.in`에 rapidfuzz 추가**

`Pillow>=10.0` 다음 줄에 추가:
```
rapidfuzz>=3.0
```

- [ ] **Step 4: rapidfuzz 설치**

```bash
pip3 install rapidfuzz --break-system-packages
```

- [ ] **Step 5: `state.py` 수정** — `NotRequired` import 추가 + 두 필드 추가

```python
"""LangGraph AgentState 정의.

원칙:
- state에 원본 이미지 bytes를 넣지 않는다.
- file_path, receipt_id, thread_id 등 ID와 경로만 저장한다.
- 재개 가능성과 checkpointer 직렬화를 위해 모든 값은 JSON-serializable이어야 한다.
"""

from datetime import date
from typing import Annotated, NotRequired

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # 식별자 — 실행 중 변경 없음
    tenant_id: int
    receipt_id: int
    file_path: str
    file_hash: str
    attempt_number: int

    # 거래일 — 법령 검색 기준
    transaction_date: date | None
    law_as_of_date: date | None  # 검색에 사용할 확정 날짜
    law_corpus_version: str

    # 처리 단계별 결과
    image_quality: str | None  # "ok" | "unreadable" | "low"
    parsed_receipt: dict | None  # ParsedReceipt.model_dump()
    retrieval_query: str | None
    relevant_laws: list[dict]  # LawChunk.model_dump() 목록

    calculation_result: dict | None  # VAT, 손금산입 계산 결과
    draft_decision: dict | None  # TaxDecision 초안
    final_decision: dict | None  # 세무사 검토 후 확정

    # 중복 감지 결과
    duplicate_suspect: NotRequired[bool]
    duplicate_receipt_ids: NotRequired[list[int]]

    # 제어 플래그
    requires_human: bool
    error_message: str | None

    # LangGraph 메시지 (add_messages reducer로 누적)
    messages: Annotated[list, add_messages]
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
DEBUG=true python3 -m pytest tests/test_vision.py::TestAgentStateDuplicateFields -v
```
Expected: PASSED

- [ ] **Step 7: 전체 테스트 확인**

```bash
DEBUG=true python3 -m pytest tests/ -q
```
Expected: 94 passed

- [ ] **Step 8: 커밋**

```bash
git add requirements/base.in src/tax_copilot/agents/state.py tests/test_vision.py
git commit -m "feat(state): add duplicate_suspect fields to AgentState and rapidfuzz dep"
```

---

## Task 2: `duplicate_check_node` 구현

**Files:**
- Create: `src/tax_copilot/agents/nodes/duplicate_check.py`
- Test: `tests/test_vision.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_vision.py`의 `TestAgentStateDuplicateFields` 아래에 추가

```python
class TestDuplicateCheckNode:
    async def test_detects_duplicate_by_name_and_amount(self) -> None:
        """동일 금액 + 유사 가맹점명 → suspect=True."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from tax_copilot.agents.nodes.duplicate_check import duplicate_check_node

        mock_receipt = MagicMock()
        mock_receipt.id = 42
        mock_receipt.parsed_data = {
            "merchant_name": "스타벅스강남점",
            "total_amount_krw": 5500,
        }

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_receipt]
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_execute_result

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        state = AgentState(
            tenant_id=1, receipt_id=1, file_path="/tmp/t.jpg",  # noqa: S108
            file_hash="abc", attempt_number=1,
            transaction_date=None, law_as_of_date=None,
            law_corpus_version="v1", image_quality="ok",
            parsed_receipt={
                "merchant_name": "스타벅스",
                "total_amount_krw": 5500,
                "extraction_confidence": 0.95,
            },
            retrieval_query=None, relevant_laws=[],
            calculation_result=None, draft_decision=None,
            final_decision=None, requires_human=False,
            error_message=None, messages=[],
        )

        with patch(
            "tax_copilot.agents.nodes.duplicate_check.AsyncSessionLocal",
            return_value=mock_cm,
        ):
            result = await duplicate_check_node(state)

        assert result["duplicate_suspect"] is True
        assert 42 in result["duplicate_receipt_ids"]

    async def test_different_amount_not_duplicate(self) -> None:
        """금액이 다르면 가맹점명이 같아도 중복 아님."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from tax_copilot.agents.nodes.duplicate_check import duplicate_check_node

        mock_receipt = MagicMock()
        mock_receipt.id = 42
        mock_receipt.parsed_data = {
            "merchant_name": "스타벅스",
            "total_amount_krw": 9900,  # 금액 다름
        }

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_receipt]
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_execute_result

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        state = AgentState(
            tenant_id=1, receipt_id=1, file_path="/tmp/t.jpg",  # noqa: S108
            file_hash="abc", attempt_number=1,
            transaction_date=None, law_as_of_date=None,
            law_corpus_version="v1", image_quality="ok",
            parsed_receipt={
                "merchant_name": "스타벅스",
                "total_amount_krw": 5500,
                "extraction_confidence": 0.95,
            },
            retrieval_query=None, relevant_laws=[],
            calculation_result=None, draft_decision=None,
            final_decision=None, requires_human=False,
            error_message=None, messages=[],
        )

        with patch(
            "tax_copilot.agents.nodes.duplicate_check.AsyncSessionLocal",
            return_value=mock_cm,
        ):
            result = await duplicate_check_node(state)

        assert result["duplicate_suspect"] is False
        assert result["duplicate_receipt_ids"] == []

    async def test_low_confidence_skips_check(self) -> None:
        """confidence < 0.75 이면 DB 조회 없이 통과."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from tax_copilot.agents.nodes.duplicate_check import duplicate_check_node

        state = AgentState(
            tenant_id=1, receipt_id=1, file_path="/tmp/t.jpg",  # noqa: S108
            file_hash="abc", attempt_number=1,
            transaction_date=None, law_as_of_date=None,
            law_corpus_version="v1", image_quality="ok",
            parsed_receipt={
                "merchant_name": "스타벅스",
                "total_amount_krw": 5500,
                "extraction_confidence": 0.5,  # 낮음
            },
            retrieval_query=None, relevant_laws=[],
            calculation_result=None, draft_decision=None,
            final_decision=None, requires_human=False,
            error_message=None, messages=[],
        )

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock()
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "tax_copilot.agents.nodes.duplicate_check.AsyncSessionLocal",
            return_value=mock_cm,
        ) as mock_session:
            result = await duplicate_check_node(state)

        mock_session.assert_not_called()
        assert result["duplicate_suspect"] is False

    async def test_no_merchant_name_skips_check(self) -> None:
        """merchant_name 없으면 중복 감지 생략."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from tax_copilot.agents.nodes.duplicate_check import duplicate_check_node

        state = AgentState(
            tenant_id=1, receipt_id=1, file_path="/tmp/t.jpg",  # noqa: S108
            file_hash="abc", attempt_number=1,
            transaction_date=None, law_as_of_date=None,
            law_corpus_version="v1", image_quality="ok",
            parsed_receipt={
                "merchant_name": None,
                "total_amount_krw": 5500,
                "extraction_confidence": 0.95,
            },
            retrieval_query=None, relevant_laws=[],
            calculation_result=None, draft_decision=None,
            final_decision=None, requires_human=False,
            error_message=None, messages=[],
        )

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock()
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "tax_copilot.agents.nodes.duplicate_check.AsyncSessionLocal",
            return_value=mock_cm,
        ) as mock_session:
            result = await duplicate_check_node(state)

        mock_session.assert_not_called()
        assert result["duplicate_suspect"] is False
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
DEBUG=true python3 -m pytest tests/test_vision.py::TestDuplicateCheckNode -v
```
Expected: ERROR — `duplicate_check` module not found

- [ ] **Step 3: `duplicate_check.py` 구현**

```python
"""중복 영수증 감지 노드.

OCR 신뢰도 >= 0.75인 경우에만 실행.
가맹점명 유사도(rapidfuzz ratio >= 80) + 금액 동일 기준으로 의심 중복 탐지.
"""

import logging

from sqlalchemy import select

from tax_copilot.agents.state import AgentState
from tax_copilot.infra.database import AsyncSessionLocal
from tax_copilot.infra.db.models.receipt import STATUS_APPROVED, STATUS_NEEDS_REVIEW, Receipt

logger = logging.getLogger(__name__)

_CONFIDENCE_THRESHOLD = 0.75
_NAME_SIMILARITY_THRESHOLD = 80


async def duplicate_check_node(state: AgentState) -> dict:
    """파싱된 영수증이 기존 영수증과 의심 중복인지 확인한다."""
    parsed = state.get("parsed_receipt") or {}
    confidence = parsed.get("extraction_confidence", 0.0)
    merchant_name = parsed.get("merchant_name")
    total_amount = parsed.get("total_amount_krw")

    if confidence < _CONFIDENCE_THRESHOLD or not merchant_name or total_amount is None:
        return {"duplicate_suspect": False, "duplicate_receipt_ids": []}

    from rapidfuzz import fuzz

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Receipt).where(
                    Receipt.tenant_id == state["tenant_id"],
                    Receipt.id != state["receipt_id"],
                    Receipt.status.in_([STATUS_APPROVED, STATUS_NEEDS_REVIEW]),
                    Receipt.parsed_data.is_not(None),
                )
            )
            candidates = result.scalars().all()
    except Exception:
        logger.exception("duplicate_check.db_error receipt_id=%s", state["receipt_id"])
        return {"duplicate_suspect": False, "duplicate_receipt_ids": []}

    duplicate_ids: list[int] = []
    for candidate in candidates:
        c_data = candidate.parsed_data or {}
        c_name = c_data.get("merchant_name")
        c_amount = c_data.get("total_amount_krw")

        if c_name is None or c_amount != total_amount:
            continue

        similarity = fuzz.ratio(merchant_name, c_name)
        if similarity >= _NAME_SIMILARITY_THRESHOLD:
            duplicate_ids.append(candidate.id)

    return {
        "duplicate_suspect": len(duplicate_ids) > 0,
        "duplicate_receipt_ids": duplicate_ids,
    }
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
DEBUG=true python3 -m pytest tests/test_vision.py::TestDuplicateCheckNode -v
```
Expected: 4 PASSED

- [ ] **Step 5: 전체 테스트 확인**

```bash
DEBUG=true python3 -m pytest tests/ -q
```
Expected: 98 passed

- [ ] **Step 6: 커밋**

```bash
git add src/tax_copilot/agents/nodes/duplicate_check.py tests/test_vision.py
git commit -m "feat(agent): add duplicate_check_node with rapidfuzz name similarity"
```

---

## Task 3: DB 모델 + Alembic 마이그레이션

**Files:**
- Modify: `src/tax_copilot/infra/db/models/receipt.py`
- Create: `alembic/versions/0003_add_duplicate_suspect.py`

- [ ] **Step 1: `receipt.py`에 컬럼 추가** — `account_code` 컬럼 바로 아래에 추가

```python
    # 계정과목 분류 결과
    account_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # 중복 감지 결과
    duplicate_suspect: Mapped[bool] = mapped_column(default=False, server_default="false")
    duplicate_receipt_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 2: 마이그레이션 파일 생성**

파일 `alembic/versions/0003_add_duplicate_suspect.py`:

```python
"""add duplicate_suspect to receipts

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "receipts",
        sa.Column(
            "duplicate_suspect",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "receipts",
        sa.Column("duplicate_receipt_ids", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("receipts", "duplicate_receipt_ids")
    op.drop_column("receipts", "duplicate_suspect")
```

- [ ] **Step 3: 커밋**

```bash
git add src/tax_copilot/infra/db/models/receipt.py \
        alembic/versions/0003_add_duplicate_suspect.py
git commit -m "feat(db): add duplicate_suspect and duplicate_receipt_ids columns"
```

---

## Task 4: 그래프에 노드 연결

**Files:**
- Modify: `src/tax_copilot/agents/graph.py`

- [ ] **Step 1: `graph.py` 수정** — import 추가 + 노드 등록 + 엣지 수정

```python
"""LangGraph 워크플로우 그래프.

구조:
  START → image_quality
    → (unreadable) → reject_unreadable → save_result → END
    → (ok)         → intake → duplicate_check → build_retrieval_query → tax_law_retrieval
                            → calculation → audit_prepare
                              → (requires_human) → human_review[interrupt] → save_result → END
                              → (auto)           → save_result → END

핵심 설계 규칙:
- audit_prepare_node: LLM 작업 수행, state에 draft_decision 저장
- human_review_node: interrupt()만 수행, LLM/DB/API 호출 금지
- save_result_node: 두 경로 공통 종착점
"""

from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node
from tax_copilot.agents.nodes.calculation import calculation_node
from tax_copilot.agents.nodes.duplicate_check import duplicate_check_node
from tax_copilot.agents.nodes.human_review import human_review_node
from tax_copilot.agents.nodes.image_quality import image_quality_node
from tax_copilot.agents.nodes.intake import intake_node
from tax_copilot.agents.nodes.retrieval import build_retrieval_query_node, tax_law_retrieval_node
from tax_copilot.agents.nodes.save_result import reject_unreadable_node, save_result_node
from tax_copilot.agents.state import AgentState


def _route_after_quality(state: AgentState) -> str:
    """이미지 품질에 따라 처리 경로를 결정한다."""
    return "reject_unreadable" if state.get("image_quality") == "unreadable" else "intake"


def _route_after_audit(state: AgentState) -> str:
    """HITL 필요 여부에 따라 경로를 결정한다."""
    return "human_review" if state.get("requires_human") else "save_result"


def build_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """그래프를 빌드하고 컴파일한다."""
    builder = StateGraph(AgentState)

    # 노드 등록
    builder.add_node("image_quality", image_quality_node)
    builder.add_node("reject_unreadable", reject_unreadable_node)
    builder.add_node("intake", intake_node)
    builder.add_node("duplicate_check", duplicate_check_node)
    builder.add_node("build_retrieval_query", build_retrieval_query_node)
    builder.add_node("tax_law_retrieval", tax_law_retrieval_node)
    builder.add_node("calculation", calculation_node)
    builder.add_node("audit_prepare", audit_prepare_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("save_result", save_result_node)

    # 엣지 연결
    builder.add_edge(START, "image_quality")
    builder.add_conditional_edges("image_quality", _route_after_quality)
    builder.add_edge("reject_unreadable", "save_result")
    builder.add_edge("intake", "duplicate_check")
    builder.add_edge("duplicate_check", "build_retrieval_query")
    builder.add_edge("build_retrieval_query", "tax_law_retrieval")
    builder.add_edge("tax_law_retrieval", "calculation")
    builder.add_edge("calculation", "audit_prepare")
    builder.add_conditional_edges("audit_prepare", _route_after_audit)
    builder.add_edge("human_review", "save_result")
    builder.add_edge("save_result", END)

    return builder.compile(checkpointer=checkpointer)


def generate_thread_id(tenant_id: int, file_hash: str, receipt_id: int, attempt_number: int) -> str:
    """고유 thread_id를 생성한다.

    재처리 시 새로운 suffix를 붙여 이전 checkpoint에서 잘못 재개되는 것을 방지한다.
    """
    suffix = uuid4().hex[:8]
    return f"t{tenant_id}-{file_hash[:8]}-r{receipt_id}-a{attempt_number}-{suffix}"
```

- [ ] **Step 2: 전체 테스트 확인**

```bash
DEBUG=true python3 -m pytest tests/ -q
```
Expected: 98 passed

- [ ] **Step 3: 커밋**

```bash
git add src/tax_copilot/agents/graph.py
git commit -m "feat(graph): wire duplicate_check_node between intake and build_retrieval_query"
```

---

## Task 5: Celery task 저장 + API 응답 노출

**Files:**
- Modify: `src/tax_copilot/workers/tasks/receipts.py`
- Modify: `src/tax_copilot/schemas/receipts.py`
- Modify: `src/tax_copilot/api/v1/receipts.py`

- [ ] **Step 1: `_run_workflow`에 duplicate 필드 저장 추가**

`if is_interrupted or requires_human:` 바로 위에 두 줄 추가 (APPROVED/NEEDS_REVIEW 모든 경로에서 저장):

```python
        # 중복 감지 결과는 경로 무관하게 저장
        receipt.duplicate_suspect = final_state.get("duplicate_suspect", False)
        receipt.duplicate_receipt_ids = final_state.get("duplicate_receipt_ids") or []

        if is_interrupted or requires_human:
            receipt.status = STATUS_NEEDS_REVIEW
        elif final_decision:
            ...
```

- [ ] **Step 2: `schemas/receipts.py`에 필드 추가**

`account_code_reason: str | None = None` 아래에 추가:

```python
    duplicate_suspect: bool = False
    duplicate_receipt_ids: list[int] = []
```

- [ ] **Step 3: `api/v1/receipts.py`의 `_to_status_response` 수정**

`account_code_reason=r.parsed_data.get("account_code_reason") if r.parsed_data else None,` 아래에 추가:

```python
        duplicate_suspect=r.duplicate_suspect,
        duplicate_receipt_ids=r.duplicate_receipt_ids or [],
```

- [ ] **Step 4: 전체 테스트 확인**

```bash
DEBUG=true python3 -m pytest tests/ -q
```
Expected: 98 passed

- [ ] **Step 5: lint + mypy 확인**

```bash
DEBUG=true ruff check src tests --output-format=concise
DEBUG=true python3 -m mypy src/tax_copilot/core
```
Expected: All checks passed, no issues

- [ ] **Step 6: 커밋**

```bash
git add src/tax_copilot/workers/tasks/receipts.py \
        src/tax_copilot/schemas/receipts.py \
        src/tax_copilot/api/v1/receipts.py
git commit -m "feat(api): persist and expose duplicate_suspect in receipt response"
```

---

## Task 6: FEATURES.md 업데이트

**Files:**
- Modify: `docs/FEATURES.md`

- [ ] **Step 1: 완료 항목 체크**

`docs/FEATURES.md` 섹션 7의 "즉시 가능" 항목 수정:

```markdown
즉시 가능 (기술 난이도 낮음, 임팩트 高)
├── [x] 경비 계정과목 분류    ← 완료
└── [x] 의미 기반 중복 감지   ← 완료
```

그리고 섹션 3.2 항목들을 완료로 표시:

```markdown
- [x] (가맹점명 + 금액) 조합 유사도 검사 (rapidfuzz ratio >= 80)
- [x] 동일 거래 의심 시 API 응답에 duplicate_suspect 플래그 포함
- [ ] 중복 의심 영수증 쌍 시각화 (추후)
```

- [ ] **Step 2: 커밋**

```bash
git add docs/FEATURES.md
git commit -m "docs: mark semantic duplicate detection as complete in FEATURES.md"
```
