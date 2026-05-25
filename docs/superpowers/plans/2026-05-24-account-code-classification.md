# 경비 계정과목 자동 분류 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `audit_prepare_node`의 기존 rule-based 로직을 확장해 영수증마다 계정과목 대분류(15종)를 자동 분류하고, DB 저장 + API 응답 + 세무사 수정 PATCH 엔드포인트를 제공한다.

**Architecture:** `AccountCode` Literal 타입을 `core/tax/schemas.py`에 정의하고, 기존 `TaxDecision.account_title(str|None)`을 `account_code(AccountCode)`로 교체한다. `audit_prepare_node`는 증빙 종류·가맹점명 패턴 기반 규칙으로 분류하며, LLM 추가 호출 없다. 분류 결과는 `Receipt.account_code` 컬럼에 저장되고 `GET /receipts/{id}`·`PATCH /receipts/{id}/account-code`로 노출된다.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, pytest-asyncio

---

## 파일 구조 (변경 대상)

| 파일 | 변경 종류 | 역할 |
|------|-----------|------|
| `src/tax_copilot/core/tax/schemas.py` | 수정 | `AccountCode` Literal + `TaxDecision` 필드 교체 |
| `src/tax_copilot/infra/db/models/receipt.py` | 수정 | `account_code` 컬럼 추가 |
| `alembic/versions/0002_add_account_code.py` | 신규 | DB 마이그레이션 |
| `src/tax_copilot/agents/nodes/audit_prepare.py` | 수정 | 분류 규칙 확장, `account_code` 사용 |
| `src/tax_copilot/agents/nodes/save_result.py` | 수정 | `account_title` → `account_code` 교체 |
| `src/tax_copilot/schemas/receipts.py` | 수정 | API 응답에 `account_code` 추가 |
| `src/tax_copilot/schemas/reviews.py` | 수정 | 검토 응답에 `account_code` 추가 |
| `src/tax_copilot/api/v1/receipts.py` | 수정 | `_to_status_response` + PATCH 엔드포인트 |
| `src/tax_copilot/api/v1/reviews.py` | 수정 | 검토 응답에 `account_code` 포함 |
| `tests/test_vision.py` | 수정 | `account_code` 검증 테스트 추가 |
| `tests/test_validation.py` | 수정 | PATCH 엔드포인트 테스트 추가 |

---

## Task 1: `AccountCode` 타입 정의 + `TaxDecision` 스키마 수정

**Files:**
- Modify: `src/tax_copilot/core/tax/schemas.py`
- Test: `tests/test_vision.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_vision.py`의 `TestParsedReceiptSchema` 클래스 아래에 추가

```python
class TestTaxDecisionAccountCode:
    def test_default_account_code_is_미분류(self) -> None:
        from tax_copilot.core.tax.schemas import TaxDecision
        decision = TaxDecision(
            requires_human_review=False,
            prompt_version="v1",
            model_name="rule-based",
            law_corpus_version="v1",
        )
        assert decision.account_code == "미분류"

    def test_valid_account_code_accepted(self) -> None:
        from tax_copilot.core.tax.schemas import TaxDecision
        decision = TaxDecision(
            account_code="접대비",
            requires_human_review=False,
            prompt_version="v1",
            model_name="rule-based",
            law_corpus_version="v1",
        )
        assert decision.account_code == "접대비"

    def test_invalid_account_code_raises(self) -> None:
        from tax_copilot.core.tax.schemas import TaxDecision
        with pytest.raises(ValueError):
            TaxDecision(
                account_code="잘못된값",
                requires_human_review=False,
                prompt_version="v1",
                model_name="rule-based",
                law_corpus_version="v1",
            )

    def test_account_code_reason_is_optional(self) -> None:
        from tax_copilot.core.tax.schemas import TaxDecision
        decision = TaxDecision(
            account_code="소모품비",
            account_code_reason="편의점 구매",
            requires_human_review=False,
            prompt_version="v1",
            model_name="rule-based",
            law_corpus_version="v1",
        )
        assert decision.account_code_reason == "편의점 구매"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
DEBUG=true python3 -m pytest tests/test_vision.py::TestTaxDecisionAccountCode -v
```
Expected: `ERROR` — `TaxDecision` has no `account_code` field yet

- [ ] **Step 3: `core/tax/schemas.py` 수정** — `AccountCode` 타입 추가, `account_title` → `account_code` 교체

```python
"""세무 판단 도메인 모델.

core/ 레이어이므로 외부 라이브러리 없음 (pydantic 허용).
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

EvidenceStatus = Literal["valid", "insufficient", "unreadable", "unknown"]

AccountCode = Literal[
    "복리후생비",
    "접대비",
    "소모품비",
    "여비교통비",
    "통신비",
    "광고선전비",
    "수선비",
    "임차료",
    "교육훈련비",
    "도서인쇄비",
    "회의비",
    "세금과공과",
    "보험료",
    "외주용역비",
    "미분류",
]


class Citation(BaseModel):
    """판단 근거로 인용한 법령 chunk."""

    chunk_id: str
    law_name: str
    article_no: str | None = None
    paragraph_no: str | None = None
    effective_from: date
    effective_to: date | None = None
    quoted_text: str


class TaxDecision(BaseModel):
    """세무 판단 결과. audit_prepare_node와 human_review_node가 생성한다."""

    vat_creditable: bool | None = Field(
        default=None,
        description="부가세 매입세액 공제 가능 여부. None은 판단 불가.",
    )
    expense_deductible: bool | None = Field(
        default=None,
        description="법인세/소득세 손금(필요경비) 산입 가능 여부.",
    )
    account_code: AccountCode = Field(
        default="미분류",
        description="경비 계정과목 대분류 (15종).",
    )
    account_code_reason: str | None = Field(
        default=None,
        description="계정과목 분류 근거 한 줄.",
    )

    evidence_type: str = "unknown"
    evidence_status: EvidenceStatus = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    risk_flags: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)

    requires_human_review: bool
    review_reason: str | None = None

    # 감사 추적용
    prompt_version: str
    model_name: str
    law_corpus_version: str

    # 계산 결과 포함 (감사 로그용)
    calculation_result: dict[str, object] | None = None

    # 세무사 검토 결과 (resume 후 채워짐)
    human_approved: bool | None = None
    human_comment: str | None = None
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
DEBUG=true python3 -m pytest tests/test_vision.py::TestTaxDecisionAccountCode -v
```
Expected: 4 PASSED

- [ ] **Step 5: 기존 테스트 깨지지 않는지 확인**

```bash
DEBUG=true python3 -m pytest tests/ -q
```
Expected: 85+ passed (일부 테스트는 `account_title` 참조로 실패할 수 있음 — Task 2에서 수정)

- [ ] **Step 6: 커밋**

```bash
git add src/tax_copilot/core/tax/schemas.py tests/test_vision.py
git commit -m "feat(schema): add AccountCode Literal type and replace account_title in TaxDecision"
```

---

## Task 2: `audit_prepare_node` 분류 규칙 확장

**Files:**
- Modify: `src/tax_copilot/agents/nodes/audit_prepare.py`
- Modify: `src/tax_copilot/agents/nodes/save_result.py`
- Test: `tests/test_vision.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_vision.py`의 `TestAuditPrepareNode` 클래스에 추가

```python
    async def test_credit_card_slip_gets_account_code(self) -> None:
        """신용카드 영수증은 account_code가 미분류가 아니어야 한다."""
        from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node

        state = _make_state_with_parsed(
            evidence_type="credit_card_slip",
            confidence=0.95,
            relevant_laws=[{"chunk_id": "vat-art38", "law_name": "부가가치세법", "article_no": "제38조"}],  # noqa: E501
        )
        result = await audit_prepare_node(state)
        draft = result["draft_decision"]
        assert "account_code" in draft
        assert draft["account_code"] != ""

    async def test_taxi_merchant_gets_여비교통비(self) -> None:
        """택시 가맹점명은 여비교통비로 분류된다."""
        from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node
        from tax_copilot.agents.state import AgentState

        state = AgentState(
            tenant_id=1, receipt_id=1, file_path="/tmp/t.jpg",
            file_hash="abc", attempt_number=1,
            transaction_date=None, law_as_of_date=None,
            law_corpus_version="v1", image_quality=None,
            parsed_receipt={
                "merchant_name": "카카오택시",
                "evidence_type": "credit_card_slip",
                "extraction_confidence": 0.95,
                "transaction_date": "2024-06-15",
            },
            retrieval_query=None,
            relevant_laws=[{"chunk_id": "c1", "law_name": "소득세법", "article_no": "제1조"}],
            calculation_result=None, draft_decision=None,
            final_decision=None, requires_human=False,
            error_message=None, messages=[],
        )
        result = await audit_prepare_node(state)
        assert result["draft_decision"]["account_code"] == "여비교통비"

    async def test_unknown_evidence_gets_미분류(self) -> None:
        """증빙 종류 불명확 → 미분류."""
        from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node
        from tax_copilot.agents.state import AgentState

        state = AgentState(
            tenant_id=1, receipt_id=1, file_path="/tmp/t.jpg",
            file_hash="abc", attempt_number=1,
            transaction_date=None, law_as_of_date=None,
            law_corpus_version="v1", image_quality=None,
            parsed_receipt={
                "merchant_name": "알수없는가맹점",
                "evidence_type": "unknown",
                "extraction_confidence": 0.5,
            },
            retrieval_query=None, relevant_laws=[],
            calculation_result=None, draft_decision=None,
            final_decision=None, requires_human=False,
            error_message=None, messages=[],
        )
        result = await audit_prepare_node(state)
        assert result["draft_decision"]["account_code"] == "미분류"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
DEBUG=true python3 -m pytest tests/test_vision.py::TestAuditPrepareNode::test_credit_card_slip_gets_account_code tests/test_vision.py::TestAuditPrepareNode::test_taxi_merchant_gets_여비교통비 tests/test_vision.py::TestAuditPrepareNode::test_unknown_evidence_gets_미분류 -v
```
Expected: 3 FAILED

- [ ] **Step 3: `audit_prepare.py` 전체 교체**

```python
"""판단 초안 생성 노드.

핵심 원칙:
- 이 노드에서 LLM 판단 초안을 만들고 state에 저장한다.
- interrupt()는 절대 이 노드에서 호출하지 않는다.
- interrupt()는 human_review_node에서만 호출한다.
- 이유: resume 시 이 노드가 재실행되면 LLM 비용이 이중 발생하고 결과가 달라질 수 있다.
"""

from tax_copilot.agents.state import AgentState
from tax_copilot.core.tax.schemas import AccountCode

_PROMPT_VERSION = "v0.3-rule-based"
_MODEL_NAME = "rule-based"

# 증빙 종류별 부가세 공제 가능 여부
_VAT_CREDITABLE_BY_EVIDENCE: dict[str, bool | None] = {
    "tax_invoice": True,
    "credit_card_slip": True,
    "cash_receipt": True,
    "invoice": False,
    "simplified_receipt": False,
    "unknown": None,
}

# 가맹점명 키워드 → 계정과목 (우선순위 순)
_MERCHANT_KEYWORD_MAP: list[tuple[list[str], AccountCode]] = [
    (["택시", "카카오택시", "우버", "타다", "주유", "주유소", "kTX", "ktx", "SRT", "srt", "버스", "지하철", "공항"], "여비교통비"),  # noqa: E501
    (["카페", "커피", "스타벅스", "이디야", "투썸", "약국", "의원", "병원", "클리닉"], "복리후생비"),
    (["식당", "음식점", "한식", "중식", "일식", "치킨", "피자", "분식", "고기", "삼겹", "갈비"], "접대비"),
    (["통신", "SKT", "KT", "LGU", "skt", "kt", "lgu", "인터넷", "핸드폰"], "통신비"),
    (["서점", "교보문고", "영풍문고", "알라딘", "예스24", "인쇄", "출력"], "도서인쇄비"),
    (["학원", "강의", "교육", "세미나", "훈련", "연수"], "교육훈련비"),
    (["광고", "홍보", "마케팅", "현수막", "배너"], "광고선전비"),
    (["임대", "임차", "월세", "주차"], "임차료"),
    (["보험"], "보험료"),
    (["수리", "수선", "AS", "as", "유지보수"], "수선비"),
    (["세금", "공과", "협회비", "회비"], "세금과공과"),
    (["용역", "프리랜서", "외주", "개발", "디자인", "번역"], "외주용역비"),
    (["편의점", "GS25", "CU", "세븐일레븐", "이마트24", "마트", "홈플러스", "이마트", "코스트코", "문구"], "소모품비"),  # noqa: E501
]

# 증빙 종류별 기본 계정과목 (키워드 매칭 실패 시 fallback)
_DEFAULT_ACCOUNT_BY_EVIDENCE: dict[str, AccountCode] = {
    "tax_invoice": "소모품비",
    "credit_card_slip": "소모품비",
    "cash_receipt": "소모품비",
    "invoice": "소모품비",
    "simplified_receipt": "소모품비",
    "unknown": "미분류",
}


def _classify_account_code(
    merchant_name: str | None,
    evidence_type: str,
) -> tuple[AccountCode, str | None]:
    """가맹점명·증빙 종류 기반으로 계정과목을 분류한다."""
    if merchant_name:
        name_lower = merchant_name.lower()
        for keywords, code in _MERCHANT_KEYWORD_MAP:
            if any(kw.lower() in name_lower for kw in keywords):
                return code, f"가맹점명 '{merchant_name}' 패턴 매칭"

    default = _DEFAULT_ACCOUNT_BY_EVIDENCE.get(evidence_type, "미분류")
    if default == "미분류":
        return "미분류", None
    return default, f"증빙 종류 '{evidence_type}' 기본값"


def _should_require_human(state: AgentState) -> tuple[bool, str | None]:
    parsed = state.get("parsed_receipt") or {}

    if not state.get("relevant_laws"):
        return True, "검색된 법령 근거가 없습니다."

    confidence = parsed.get("extraction_confidence", 0.0)
    if confidence < 0.75:
        return True, f"추출 신뢰도가 낮습니다: {confidence:.2f}"

    if state.get("calculation_result") is None and parsed.get("supply_value_krw") is not None:
        return True, "세액 계산에 실패했습니다."

    if parsed.get("evidence_type", "unknown") == "unknown":
        return True, "증빙 종류를 판별할 수 없습니다."

    return False, None


def _build_risk_flags(parsed: dict) -> list[str]:
    flags: list[str] = []
    evidence_type = parsed.get("evidence_type", "unknown")
    total = parsed.get("total_amount_krw") or 0

    if evidence_type == "simplified_receipt" and total > 30000:
        flags.append("simplified_receipt_over_30k")

    if not parsed.get("transaction_date"):
        flags.append("missing_transaction_date")

    if evidence_type == "tax_invoice" and not parsed.get("merchant_business_no"):
        flags.append("missing_business_no_on_tax_invoice")

    return flags


async def audit_prepare_node(state: AgentState) -> dict:
    """판단 초안을 생성하고 HITL 필요 여부를 결정한다."""
    parsed = state.get("parsed_receipt") or {}
    calc = state.get("calculation_result")
    laws = state.get("relevant_laws", [])
    evidence_type = parsed.get("evidence_type", "unknown")
    merchant_name = parsed.get("merchant_name")

    requires_human, review_reason = _should_require_human(state)
    risk_flags = _build_risk_flags(parsed)

    if risk_flags and not requires_human:
        requires_human = True
        review_reason = f"위험 플래그 발견: {', '.join(risk_flags)}"

    vat_creditable = None if requires_human else _VAT_CREDITABLE_BY_EVIDENCE.get(evidence_type)
    account_code, account_code_reason = _classify_account_code(merchant_name, evidence_type)

    draft = {
        "vat_creditable": vat_creditable,
        "expense_deductible": None if requires_human else True,
        "account_code": account_code,
        "account_code_reason": account_code_reason,
        "evidence_type": evidence_type,
        "evidence_status": "valid" if parsed.get("merchant_name") else "unknown",
        "confidence": parsed.get("extraction_confidence", 0.0),
        "risk_flags": risk_flags,
        "citations": [
            {
                "chunk_id": law.get("chunk_id"),
                "law_name": law.get("law_name"),
                "article_no": law.get("article_no"),
            }
            for law in laws
        ],
        "requires_human_review": requires_human,
        "review_reason": review_reason,
        "prompt_version": _PROMPT_VERSION,
        "model_name": _MODEL_NAME,
        "law_corpus_version": state.get("law_corpus_version", "unknown"),
        "calculation_result": calc,
    }

    return {
        "draft_decision": draft,
        "requires_human": requires_human,
    }
```

- [ ] **Step 4: `save_result.py`의 `account_title` → `account_code` 교체**

```python
"""결과 저장 노드."""

from tax_copilot.agents.state import AgentState


async def save_result_node(state: AgentState) -> dict:
    """워크플로우 완료를 표시한다."""
    if state.get("final_decision") is None:
        draft = state.get("draft_decision") or {}
        return {
            "final_decision": {
                **draft,
                "human_approved": None,
                "human_comment": None,
                "requires_human_review": False,
            }
        }
    return {}


async def reject_unreadable_node(state: AgentState) -> dict:
    """판독 불가 이미지를 처리한다."""
    return {
        "final_decision": {
            "vat_creditable": None,
            "expense_deductible": None,
            "account_code": "미분류",
            "account_code_reason": None,
            "evidence_type": "unknown",
            "evidence_status": "unreadable",
            "confidence": 0.0,
            "risk_flags": ["image_unreadable"],
            "citations": [],
            "requires_human_review": True,
            "review_reason": state.get("error_message") or "이미지를 판독할 수 없습니다.",
            "human_approved": None,
            "human_comment": None,
        },
        "requires_human": True,
    }
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
DEBUG=true python3 -m pytest tests/test_vision.py -v
```
Expected: 모두 PASSED

- [ ] **Step 6: 전체 테스트 확인**

```bash
DEBUG=true python3 -m pytest tests/ -q
```
Expected: 85+ passed

- [ ] **Step 7: 커밋**

```bash
git add src/tax_copilot/agents/nodes/audit_prepare.py \
        src/tax_copilot/agents/nodes/save_result.py \
        tests/test_vision.py
git commit -m "feat(agent): extend audit_prepare_node with account code classification rules"
```

---

## Task 3: DB 모델 + Alembic 마이그레이션

**Files:**
- Modify: `src/tax_copilot/infra/db/models/receipt.py`
- Create: `alembic/versions/0002_add_account_code.py`

- [ ] **Step 1: `receipt.py`에 `account_code` 컬럼 추가**

`created_at` 컬럼 바로 위에 추가:

```python
    # 계정과목 분류 결과
    account_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

- [ ] **Step 2: Alembic 마이그레이션 파일 생성**

파일 `alembic/versions/0002_add_account_code.py` 내용:

```python
"""add account_code to receipts

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "receipts",
        sa.Column("account_code", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("receipts", "account_code")
```

- [ ] **Step 3: 마이그레이션 파일에 올바른 `down_revision` 확인**

```bash
head -10 /home/sthun11/Tax_Agent/alembic/versions/0001_initial_core_schema.py
```
`revision` 값을 확인해 `down_revision`에 정확히 기입한다.

- [ ] **Step 4: 커밋**

```bash
git add src/tax_copilot/infra/db/models/receipt.py \
        alembic/versions/0002_add_account_code.py
git commit -m "feat(db): add account_code column to receipts table"
```

---

## Task 4: `save_result_node`에서 DB 저장 연결

현재 `Receipt.account_code` 저장은 Celery task(`_run_workflow`)에서 `final_decision`을 읽어 DB에 쓰는 구조다.

**Files:**
- Modify: `src/tax_copilot/workers/tasks/receipts.py`

- [ ] **Step 1: `_run_workflow`의 DB 업데이트 블록에 `account_code` 추가**

`receipts.py`의 "3. 결과를 DB에 저장" 블록에서 `receipt.parsed_data = final_decision` 아래에 추가:

```python
        if is_interrupted or requires_human:
            receipt.status = STATUS_NEEDS_REVIEW
        elif final_decision:
            receipt.status = STATUS_APPROVED
            receipt.parsed_data = final_decision
            receipt.account_code = final_decision.get("account_code")  # 추가
            tx_date = final_state.get("transaction_date")
            if tx_date is not None:
                receipt.transaction_date = tx_date
        else:
            receipt.status = STATUS_FAILED
            receipt.error_message = "워크플로우가 결과를 반환하지 않았습니다."
```

- [ ] **Step 2: 전체 테스트 확인**

```bash
DEBUG=true python3 -m pytest tests/ -q
```
Expected: 85+ passed

- [ ] **Step 3: 커밋**

```bash
git add src/tax_copilot/workers/tasks/receipts.py
git commit -m "feat(worker): persist account_code to Receipt on workflow completion"
```

---

## Task 5: API 응답 스키마 + `_to_status_response` 수정

**Files:**
- Modify: `src/tax_copilot/schemas/receipts.py`
- Modify: `src/tax_copilot/schemas/reviews.py`
- Modify: `src/tax_copilot/api/v1/receipts.py`
- Modify: `src/tax_copilot/api/v1/reviews.py`

- [ ] **Step 1: `schemas/receipts.py`에 필드 추가**

`ReceiptStatusResponse`에 `review_comment` 아래에 추가:

```python
    account_code: str | None = None
    account_code_reason: str | None = None
```

- [ ] **Step 2: `schemas/reviews.py`에 필드 추가**

`ReviewHistoryItem`에 `transaction_date` 아래에 추가:

```python
    account_code: str | None = None
```

- [ ] **Step 3: `api/v1/receipts.py`의 `_to_status_response` 수정**

`review_comment=r.review_comment,` 아래에 추가:

```python
        account_code=r.account_code,
        account_code_reason=r.parsed_data.get("account_code_reason") if r.parsed_data else None,
```

- [ ] **Step 4: `api/v1/reviews.py`의 히스토리 응답에 `account_code` 추가**

`reviews.py`에서 `ReviewHistoryItem` 생성 부분에 `account_code=r.account_code` 추가.
해당 위치 확인:

```bash
grep -n "ReviewHistoryItem" /home/sthun11/Tax_Agent/src/tax_copilot/api/v1/reviews.py
```

- [ ] **Step 5: 전체 테스트 확인**

```bash
DEBUG=true python3 -m pytest tests/ -q
```
Expected: 85+ passed

- [ ] **Step 6: 커밋**

```bash
git add src/tax_copilot/schemas/receipts.py \
        src/tax_copilot/schemas/reviews.py \
        src/tax_copilot/api/v1/receipts.py \
        src/tax_copilot/api/v1/reviews.py
git commit -m "feat(api): expose account_code in receipt and review responses"
```

---

## Task 6: `PATCH /v1/receipts/{id}/account-code` 엔드포인트

**Files:**
- Modify: `src/tax_copilot/api/v1/receipts.py`
- Modify: `src/tax_copilot/schemas/receipts.py`
- Test: `tests/test_validation.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_validation.py` 맨 아래에 추가

```python
class TestAccountCodePatch:
    """PATCH /v1/receipts/{id}/account-code 엔드포인트 검증."""

    @pytest.mark.asyncio
    async def test_valid_account_code_accepted(self) -> None:
        """유효한 계정과목으로 PATCH 시 200 반환."""
        from tax_copilot.core.tax.schemas import AccountCode
        from tax_copilot.schemas.receipts import AccountCodeUpdateRequest

        req = AccountCodeUpdateRequest(account_code="접대비")
        assert req.account_code == "접대비"

    @pytest.mark.asyncio
    async def test_invalid_account_code_rejected(self) -> None:
        """15종 외 계정과목은 ValidationError."""
        from tax_copilot.schemas.receipts import AccountCodeUpdateRequest

        with pytest.raises(ValueError):
            AccountCodeUpdateRequest(account_code="잘못된값")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
DEBUG=true python3 -m pytest tests/test_validation.py::TestAccountCodePatch -v
```
Expected: ERROR — `AccountCodeUpdateRequest` not defined

- [ ] **Step 3: `schemas/receipts.py`에 요청 스키마 추가**

파일 맨 아래에 추가:

```python
from tax_copilot.core.tax.schemas import AccountCode


class AccountCodeUpdateRequest(BaseModel):
    account_code: AccountCode
```

- [ ] **Step 4: `api/v1/receipts.py`에 PATCH 엔드포인트 추가**

파일 맨 아래에 추가 (import에 `AccountCodeUpdateRequest`, `record_event`, `ACCOUNT_CODE_UPDATED` 추가 필요):

먼저 `infra/db/models/audit_event.py`에 상수 추가:

```python
ACCOUNT_CODE_UPDATED = "account_code_updated"
```

그 다음 `api/v1/receipts.py` import 블록에 추가:

```python
from tax_copilot.infra.db.models.audit_event import ACCOUNT_CODE_UPDATED, RECEIPT_UPLOADED
from tax_copilot.schemas.receipts import (
    AccountCodeUpdateRequest,
    ReceiptListResponse,
    ReceiptStatusResponse,
    ReceiptUploadResponse,
)
```

엔드포인트:

```python
@router.patch("/{receipt_id}/account-code", response_model=ReceiptStatusResponse)
async def update_account_code(
    receipt_id: int,
    body: AccountCodeUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptStatusResponse:
    """세무사가 계정과목을 직접 수정 확정한다."""
    result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id,
            Receipt.tenant_id == current_user.tenant_id,
        )
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise ValidationError(f"영수증 {receipt_id}를 찾을 수 없습니다.")

    old_code = receipt.account_code
    receipt.account_code = body.account_code

    await record_event(
        db,
        tenant_id=current_user.tenant_id,
        event_type=ACCOUNT_CODE_UPDATED,
        actor_user_id=current_user.user_id,
        receipt_id=receipt.id,
        payload={"old": old_code, "new": body.account_code},
    )

    await db.commit()
    await db.refresh(receipt)

    logger.info(
        "receipt.account_code_updated",
        receipt_id=receipt_id,
        old=old_code,
        new=body.account_code,
    )
    return _to_status_response(receipt)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
DEBUG=true python3 -m pytest tests/test_validation.py::TestAccountCodePatch -v
```
Expected: 2 PASSED

- [ ] **Step 6: 전체 테스트 확인**

```bash
DEBUG=true python3 -m pytest tests/ -q
```
Expected: 87+ passed

- [ ] **Step 7: lint 확인**

```bash
DEBUG=true ruff check src tests --output-format=concise
```
Expected: All checks passed

- [ ] **Step 8: 커밋**

```bash
git add src/tax_copilot/schemas/receipts.py \
        src/tax_copilot/api/v1/receipts.py \
        src/tax_copilot/infra/db/models/audit_event.py \
        tests/test_validation.py
git commit -m "feat(api): add PATCH /receipts/{id}/account-code endpoint with audit log"
```

---

## Task 7: 최종 검증

- [ ] **Step 1: 전체 테스트 + lint + mypy**

```bash
DEBUG=true python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
DEBUG=true ruff check src tests --output-format=concise
DEBUG=true python3 -m mypy src/tax_copilot/core
```
Expected: 모두 통과, 오류 없음

- [ ] **Step 2: FEATURES.md 업데이트** — 구현 완료 항목 체크

`docs/FEATURES.md` 섹션 3.1의 첫 두 항목을 완료로 표시:

```markdown
- [x] 계정과목 스키마 정의 (복리후생비·접대비·소모품비·여비교통비·통신비 등 15종)
- [x] audit_prepare 노드에 계정과목 분류 추가 (rule-based, 키워드 + 증빙 종류)
- [x] 세무사 수정 확정 PATCH API
- [ ] 업무용/비업무용 분리 (다음 Sprint)
- [ ] 회계 프로그램 export 형식 (다음 Sprint)
```

- [ ] **Step 3: 최종 커밋**

```bash
git add docs/FEATURES.md
git commit -m "docs: mark account code classification as complete in FEATURES.md"
```
