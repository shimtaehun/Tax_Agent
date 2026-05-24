"""Phase 4 Vision 파이프라인 테스트.

Gemini API 없이 mock으로 전체 흐름을 검증한다.
- ParsedReceipt 스키마 검증
- image_quality_node: Pillow 체크 (실제 이미지 파일 사용)
- intake_node: Gemini mock → ParsedReceipt 변환
- audit_prepare_node: risk_flags, evidence_type 기반 HITL 조건
"""

import os
import tempfile
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from tax_copilot.agents.state import AgentState
from tax_copilot.core.receipts.schemas import ParsedReceipt

# ──────────────────────────────────────────────────────────────────────────────
# 테스트용 이미지 파일 생성 헬퍼
# ──────────────────────────────────────────────────────────────────────────────


def _make_jpeg(width: int = 100, height: int = 100) -> bytes:
    """최소 JPEG 파일을 생성한다. Pillow로 열 수 있는 유효한 파일."""
    import io

    from PIL import Image

    img = Image.new("RGB", (width, height), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_png(width: int = 100, height: int = 100) -> bytes:
    """최소 PNG 파일을 생성한다."""
    import io

    from PIL import Image

    img = Image.new("RGB", (width, height), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def valid_jpeg_file():
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(_make_jpeg(200, 200))
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def tiny_jpeg_file():
    """1KB 미만 파일."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff" + b"\x00" * 100)  # 103 bytes
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def corrupt_jpeg_file():
    """헤더는 JPEG지만 내용이 손상된 파일."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff" + b"\x00" * 2048)  # 유효하지 않은 JPEG
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def tiny_resolution_jpeg():
    """10×10 해상도 (최소 64×64 미만)."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(_make_jpeg(10, 10))
        path = f.name
    yield path
    os.unlink(path)


# ──────────────────────────────────────────────────────────────────────────────
# ParsedReceipt 스키마 테스트
# ──────────────────────────────────────────────────────────────────────────────


class TestParsedReceiptSchema:
    def test_valid_receipt(self) -> None:
        r = ParsedReceipt(
            merchant_name="테스트 카페",
            transaction_date=date(2024, 6, 15),
            total_amount_krw=11000,
            supply_value_krw=10000,
            vat_amount_krw=1000,
            payment_method="신용카드",
            evidence_type="credit_card_slip",
            extraction_confidence=0.95,
        )
        assert r.evidence_type == "credit_card_slip"
        assert r.extraction_confidence == 0.95

    def test_date_from_string(self) -> None:
        """ISO 문자열로 date 필드를 설정할 수 있다."""
        r = ParsedReceipt(
            transaction_date="2024-06-15",
            extraction_confidence=0.9,
        )
        assert r.transaction_date == date(2024, 6, 15)

    def test_invalid_date_string_becomes_none(self) -> None:
        """파싱 불가한 날짜 문자열은 None이 된다."""
        r = ParsedReceipt(
            transaction_date="not-a-date",
            extraction_confidence=0.5,
        )
        assert r.transaction_date is None

    def test_amount_from_string(self) -> None:
        """'10,000원' 같은 문자열 금액을 정수로 변환한다."""
        r = ParsedReceipt(
            total_amount_krw="11,000",
            supply_value_krw="10,000원",
            extraction_confidence=0.9,
        )
        assert r.total_amount_krw == 11000
        assert r.supply_value_krw == 10000

    def test_confidence_clamped(self) -> None:
        """confidence는 0~1 사이여야 한다."""
        with pytest.raises(ValueError):
            ParsedReceipt(extraction_confidence=1.5)

    def test_model_dump_json_serializable(self) -> None:
        """model_dump(mode='json')는 AgentState에 넣을 수 있는 dict를 반환한다."""
        r = ParsedReceipt(
            transaction_date=date(2024, 6, 15),
            extraction_confidence=0.9,
        )
        d = r.model_dump(mode="json")
        assert isinstance(d["transaction_date"], str)  # "2024-06-15"
        assert d["extraction_confidence"] == 0.9


# ──────────────────────────────────────────────────────────────────────────────
# image_quality_node 테스트
# ──────────────────────────────────────────────────────────────────────────────


class TestImageQualityNode:
    async def test_valid_jpeg_is_ok(self, valid_jpeg_file: str) -> None:
        from tax_copilot.agents.nodes.image_quality import image_quality_node

        state = _make_state(valid_jpeg_file)
        result = await image_quality_node(state)
        assert result["image_quality"] == "ok"
        assert result.get("error_message") is None

    async def test_tiny_file_is_unreadable(self, tiny_jpeg_file: str) -> None:
        from tax_copilot.agents.nodes.image_quality import image_quality_node

        state = _make_state(tiny_jpeg_file)
        result = await image_quality_node(state)
        assert result["image_quality"] == "unreadable"

    async def test_corrupt_file_is_unreadable(self, corrupt_jpeg_file: str) -> None:
        from tax_copilot.agents.nodes.image_quality import image_quality_node

        state = _make_state(corrupt_jpeg_file)
        result = await image_quality_node(state)
        assert result["image_quality"] == "unreadable"

    async def test_tiny_resolution_is_unreadable(self, tiny_resolution_jpeg: str) -> None:
        from tax_copilot.agents.nodes.image_quality import image_quality_node

        state = _make_state(tiny_resolution_jpeg)
        result = await image_quality_node(state)
        assert result["image_quality"] == "unreadable"

    async def test_nonexistent_file_is_unreadable(self) -> None:
        from tax_copilot.agents.nodes.image_quality import image_quality_node

        state = _make_state("/nonexistent/path.jpg")
        result = await image_quality_node(state)
        assert result["image_quality"] == "unreadable"

    async def test_pdf_skips_pillow_check(self) -> None:
        """PDF는 Pillow 체크 없이 ok를 반환한다."""
        from tax_copilot.agents.nodes.image_quality import image_quality_node

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF" + b"\x00" * 2048)
            path = f.name

        try:
            state = _make_state(path)
            result = await image_quality_node(state)
            assert result["image_quality"] == "ok"
        finally:
            os.unlink(path)


# ──────────────────────────────────────────────────────────────────────────────
# intake_node 테스트
# ──────────────────────────────────────────────────────────────────────────────


class TestIntakeNode:
    async def test_fallback_when_no_api_key(self, valid_jpeg_file: str) -> None:
        """Gemini API 키 없으면 confidence=0 fallback → HITL 경로."""
        from tax_copilot.agents.nodes.intake import intake_node

        state = _make_state(valid_jpeg_file)
        result = await intake_node(state)

        parsed = result["parsed_receipt"]
        assert parsed["extraction_confidence"] == 0.0
        assert result["law_as_of_date"] is not None  # fallback은 오늘 날짜

    async def test_successful_gemini_extraction(self, valid_jpeg_file: str) -> None:
        """Gemini mock이 ParsedReceipt를 반환하면 state가 올바르게 채워진다."""
        from tax_copilot.agents.nodes.intake import intake_node

        mock_receipt = ParsedReceipt(
            merchant_name="스타벅스",
            transaction_date=date(2024, 6, 15),
            total_amount_krw=5500,
            supply_value_krw=5000,
            vat_amount_krw=500,
            payment_method="신용카드",
            evidence_type="credit_card_slip",
            extraction_confidence=0.95,
        )

        with patch(
            "tax_copilot.agents.nodes.intake._extract_with_gemini",
            new_callable=AsyncMock,
            return_value=mock_receipt,
        ):
            state = _make_state(valid_jpeg_file)
            result = await intake_node(state)

        assert result["parsed_receipt"]["merchant_name"] == "스타벅스"
        assert result["parsed_receipt"]["extraction_confidence"] == 0.95
        assert result["transaction_date"] == date(2024, 6, 15)
        assert result["law_as_of_date"] == date(2024, 6, 15)

    async def test_law_as_of_date_falls_back_to_today_when_date_missing(
        self, valid_jpeg_file: str
    ) -> None:
        """거래일이 없으면 law_as_of_date가 오늘 날짜로 설정된다."""
        from tax_copilot.agents.nodes.intake import intake_node

        mock_receipt = ParsedReceipt(
            transaction_date=None,
            extraction_confidence=0.3,
        )

        with patch(
            "tax_copilot.agents.nodes.intake._extract_with_gemini",
            new_callable=AsyncMock,
            return_value=mock_receipt,
        ):
            state = _make_state(valid_jpeg_file)
            result = await intake_node(state)

        assert result["transaction_date"] is None
        assert result["law_as_of_date"] is not None


# ──────────────────────────────────────────────────────────────────────────────
# audit_prepare_node 테스트
# ──────────────────────────────────────────────────────────────────────────────


class TestAuditPrepareNode:
    async def test_no_laws_requires_human(self) -> None:
        """법령 없으면 HITL."""
        from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node

        state = _make_state_with_parsed(
            evidence_type="credit_card_slip",
            confidence=0.95,
            relevant_laws=[],
        )
        result = await audit_prepare_node(state)
        assert result["requires_human"] is True
        assert "법령" in result["draft_decision"]["review_reason"]

    async def test_low_confidence_requires_human(self) -> None:
        """신뢰도 낮으면 HITL."""
        from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node

        state = _make_state_with_parsed(
            evidence_type="credit_card_slip",
            confidence=0.5,
            relevant_laws=[{"chunk_id": "vat-art38", "law_name": "부가가치세법"}],
        )
        result = await audit_prepare_node(state)
        assert result["requires_human"] is True
        assert "신뢰도" in result["draft_decision"]["review_reason"]

    async def test_credit_card_slip_vat_creditable(self) -> None:
        """신용카드 매출전표 + 법령 있음 + 신뢰도 높음 → vat_creditable=True."""
        from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node

        state = _make_state_with_parsed(
            evidence_type="credit_card_slip",
            confidence=0.95,
            relevant_laws=[
                {"chunk_id": "vat-art38", "law_name": "부가가치세법", "article_no": "제38조"}
            ],  # noqa: E501
        )
        result = await audit_prepare_node(state)
        assert result["requires_human"] is False
        assert result["draft_decision"]["vat_creditable"] is True

    async def test_invoice_not_vat_creditable(self) -> None:
        """계산서(면세)는 vat_creditable=False."""
        from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node

        state = _make_state_with_parsed(
            evidence_type="invoice",
            confidence=0.95,
            relevant_laws=[
                {"chunk_id": "vat-art38", "law_name": "부가가치세법", "article_no": "제38조"}
            ],  # noqa: E501
        )
        result = await audit_prepare_node(state)
        assert result["requires_human"] is False
        assert result["draft_decision"]["vat_creditable"] is False

    async def test_simplified_receipt_over_30k_has_risk_flag(self) -> None:
        """간이영수증 + 3만원 초과 → risk_flag + HITL."""
        from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node

        state = _make_state_with_parsed(
            evidence_type="simplified_receipt",
            confidence=0.95,
            relevant_laws=[
                {"chunk_id": "vat-art39", "law_name": "부가가치세법", "article_no": "제39조"}
            ],  # noqa: E501
            total_amount_krw=50000,
        )
        result = await audit_prepare_node(state)
        assert "simplified_receipt_over_30k" in result["draft_decision"]["risk_flags"]
        assert result["requires_human"] is True

    async def test_missing_transaction_date_has_risk_flag(self) -> None:
        """거래일 없으면 risk_flag."""
        from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node

        state = _make_state_with_parsed(
            evidence_type="credit_card_slip",
            confidence=0.95,
            relevant_laws=[
                {"chunk_id": "vat-art38", "law_name": "부가가치세법", "article_no": "제38조"}
            ],  # noqa: E501
            transaction_date=None,
        )
        result = await audit_prepare_node(state)
        assert "missing_transaction_date" in result["draft_decision"]["risk_flags"]

    async def test_citations_included(self) -> None:
        """법령 목록이 citations에 포함된다."""
        from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node

        laws = [
            {"chunk_id": "vat-art38", "law_name": "부가가치세법", "article_no": "제38조"},
            {"chunk_id": "cit-art25", "law_name": "법인세법", "article_no": "제25조"},
        ]
        state = _make_state_with_parsed(
            evidence_type="credit_card_slip",
            confidence=0.95,
            relevant_laws=laws,
        )
        result = await audit_prepare_node(state)
        citations = result["draft_decision"]["citations"]
        assert len(citations) == 2
        assert citations[0]["chunk_id"] == "vat-art38"

    async def test_credit_card_slip_gets_account_code(self) -> None:
        """신용카드 영수증은 account_code가 빈 문자열이 아니어야 한다."""
        from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node

        state = _make_state_with_parsed(
            evidence_type="credit_card_slip",
            confidence=0.95,
            relevant_laws=[
                {"chunk_id": "vat-art38", "law_name": "부가가치세법", "article_no": "제38조"}
            ],  # noqa: E501
        )
        result = await audit_prepare_node(state)
        draft = result["draft_decision"]
        assert "account_code" in draft
        assert draft["account_code"] != ""

    async def test_taxi_merchant_gets_여비교통비(self) -> None:
        """택시 가맹점명은 여비교통비로 분류된다."""
        from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node

        state = AgentState(
            tenant_id=1,
            receipt_id=1,
            file_path="/tmp/t.jpg",  # noqa: S108
            file_hash="abc",
            attempt_number=1,
            transaction_date=None,
            law_as_of_date=None,
            law_corpus_version="v1",
            image_quality=None,
            parsed_receipt={
                "merchant_name": "카카오택시",
                "evidence_type": "credit_card_slip",
                "extraction_confidence": 0.95,
                "transaction_date": "2024-06-15",
            },
            retrieval_query=None,
            relevant_laws=[{"chunk_id": "c1", "law_name": "소득세법", "article_no": "제1조"}],
            calculation_result=None,
            draft_decision=None,
            final_decision=None,
            requires_human=False,
            error_message=None,
            messages=[],
        )
        result = await audit_prepare_node(state)
        assert result["draft_decision"]["account_code"] == "여비교통비"

    async def test_unknown_evidence_gets_미분류(self) -> None:
        """증빙 종류 불명확 → 미분류."""
        from tax_copilot.agents.nodes.audit_prepare import audit_prepare_node

        state = AgentState(
            tenant_id=1,
            receipt_id=1,
            file_path="/tmp/t.jpg",  # noqa: S108
            file_hash="abc",
            attempt_number=1,
            transaction_date=None,
            law_as_of_date=None,
            law_corpus_version="v1",
            image_quality=None,
            parsed_receipt={
                "merchant_name": "알수없는가맹점",
                "evidence_type": "unknown",
                "extraction_confidence": 0.5,
            },
            retrieval_query=None,
            relevant_laws=[],
            calculation_result=None,
            draft_decision=None,
            final_decision=None,
            requires_human=False,
            error_message=None,
            messages=[],
        )
        result = await audit_prepare_node(state)
        assert result["draft_decision"]["account_code"] == "미분류"


# ──────────────────────────────────────────────────────────────────────────────
# TaxDecision AccountCode 테스트
# ──────────────────────────────────────────────────────────────────────────────


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


# ──────────────────────────────────────────────────────────────────────────────
# AgentState duplicate 필드 테스트
# ──────────────────────────────────────────────────────────────────────────────


class TestAgentStateDuplicateFields:
    def test_state_has_duplicate_suspect_field(self) -> None:
        from tax_copilot.agents.state import AgentState

        state = AgentState(
            tenant_id=1,
            receipt_id=1,
            file_path="/tmp/t.jpg",  # noqa: S108
            file_hash="abc",
            attempt_number=1,
            transaction_date=None,
            law_as_of_date=None,
            law_corpus_version="v1",
            image_quality=None,
            parsed_receipt=None,
            retrieval_query=None,
            relevant_laws=[],
            calculation_result=None,
            draft_decision=None,
            final_decision=None,
            requires_human=False,
            error_message=None,
            messages=[],
            duplicate_suspect=True,
            duplicate_receipt_ids=[42, 99],
        )
        assert state["duplicate_suspect"] is True
        assert state["duplicate_receipt_ids"] == [42, 99]


# ──────────────────────────────────────────────────────────────────────────────
# duplicate_check_node 테스트
# ──────────────────────────────────────────────────────────────────────────────


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
            tenant_id=1,
            receipt_id=1,
            file_path="/tmp/t.jpg",  # noqa: S108
            file_hash="abc",
            attempt_number=1,
            transaction_date=None,
            law_as_of_date=None,
            law_corpus_version="v1",
            image_quality="ok",
            parsed_receipt={
                "merchant_name": "스타벅스",
                "total_amount_krw": 5500,
                "extraction_confidence": 0.95,
            },
            retrieval_query=None,
            relevant_laws=[],
            calculation_result=None,
            draft_decision=None,
            final_decision=None,
            requires_human=False,
            error_message=None,
            messages=[],
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
            "total_amount_krw": 9900,
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
            tenant_id=1,
            receipt_id=1,
            file_path="/tmp/t.jpg",  # noqa: S108
            file_hash="abc",
            attempt_number=1,
            transaction_date=None,
            law_as_of_date=None,
            law_corpus_version="v1",
            image_quality="ok",
            parsed_receipt={
                "merchant_name": "스타벅스",
                "total_amount_krw": 5500,
                "extraction_confidence": 0.95,
            },
            retrieval_query=None,
            relevant_laws=[],
            calculation_result=None,
            draft_decision=None,
            final_decision=None,
            requires_human=False,
            error_message=None,
            messages=[],
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
            tenant_id=1,
            receipt_id=1,
            file_path="/tmp/t.jpg",  # noqa: S108
            file_hash="abc",
            attempt_number=1,
            transaction_date=None,
            law_as_of_date=None,
            law_corpus_version="v1",
            image_quality="ok",
            parsed_receipt={
                "merchant_name": "스타벅스",
                "total_amount_krw": 5500,
                "extraction_confidence": 0.5,
            },
            retrieval_query=None,
            relevant_laws=[],
            calculation_result=None,
            draft_decision=None,
            final_decision=None,
            requires_human=False,
            error_message=None,
            messages=[],
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
            tenant_id=1,
            receipt_id=1,
            file_path="/tmp/t.jpg",  # noqa: S108
            file_hash="abc",
            attempt_number=1,
            transaction_date=None,
            law_as_of_date=None,
            law_corpus_version="v1",
            image_quality="ok",
            parsed_receipt={
                "merchant_name": None,
                "total_amount_krw": 5500,
                "extraction_confidence": 0.95,
            },
            retrieval_query=None,
            relevant_laws=[],
            calculation_result=None,
            draft_decision=None,
            final_decision=None,
            requires_human=False,
            error_message=None,
            messages=[],
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


# ──────────────────────────────────────────────────────────────────────────────
# 헬퍼 함수
# ──────────────────────────────────────────────────────────────────────────────


def _make_state(file_path: str) -> AgentState:
    from tax_copilot.agents.state import AgentState

    return AgentState(
        tenant_id=1,
        receipt_id=1,
        file_path=file_path,
        file_hash="abc123",
        attempt_number=1,
        transaction_date=None,
        law_as_of_date=None,
        law_corpus_version="test",
        image_quality=None,
        parsed_receipt=None,
        retrieval_query=None,
        relevant_laws=[],
        calculation_result=None,
        draft_decision=None,
        final_decision=None,
        requires_human=False,
        error_message=None,
        messages=[],
    )


def _make_state_with_parsed(
    evidence_type: str,
    confidence: float,
    relevant_laws: list,
    total_amount_krw: int | None = None,
    transaction_date: str | None = "2024-06-15",
) -> AgentState:
    from tax_copilot.agents.state import AgentState

    parsed = {
        "merchant_name": "테스트 상점",
        "merchant_business_no": "123-45-67890",
        "transaction_date": transaction_date,
        "total_amount_krw": total_amount_krw,
        "supply_value_krw": None,
        "vat_amount_krw": None,
        "payment_method": "신용카드",
        "evidence_type": evidence_type,
        "extraction_confidence": confidence,
    }

    return AgentState(
        tenant_id=1,
        receipt_id=1,
        file_path="/tmp/test.jpg",  # noqa: S108
        file_hash="abc123",
        attempt_number=1,
        transaction_date=date(2024, 6, 15) if transaction_date else None,
        law_as_of_date=date(2024, 6, 15),
        law_corpus_version="test-v1",
        image_quality="ok",
        parsed_receipt=parsed,
        retrieval_query="부가세 매입세액 공제",
        relevant_laws=relevant_laws,
        calculation_result=None,
        draft_decision=None,
        final_decision=None,
        requires_human=False,
        error_message=None,
        messages=[],
    )
