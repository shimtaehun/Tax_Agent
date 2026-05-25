"""영수증 정보 추출 노드 (Vision).

Phase 4: Gemini Vision structured output으로 실제 영수증 파싱.
Gemini API 없거나 실패하면 ExternalServiceError → requires_human=True(HITL fallback).

fallback 시에도 파이프라인이 멈추지 않는다. audit_prepare_node가 relevant_laws
없음 + confidence 낮음을 감지해 HITL로 자동 전환한다.
"""

from datetime import date

from tax_copilot.agents.state import AgentState
from tax_copilot.core.receipts.schemas import ParsedReceipt


def _fallback_receipt() -> ParsedReceipt:
    """Gemini 실패 시 사용하는 기본 ParsedReceipt. confidence=0.0으로 HITL 유도."""
    return ParsedReceipt(
        merchant_name=None,
        transaction_date=None,
        total_amount_krw=None,
        evidence_type="unknown",
        extraction_confidence=0.0,
    )


async def intake_node(state: AgentState) -> dict:
    """영수증에서 거래 정보를 추출한다.

    Gemini Vision 성공 시: 실제 추출 데이터 반환.
    Gemini Vision 실패 시: confidence=0.0 fallback → HITL 경로.
    """
    file_path = state["file_path"]

    parsed = await _extract_with_gemini(file_path)

    # transaction_date가 있으면 거래일 기준 법령 검색, 없으면 오늘 날짜
    tx_date: date | None = parsed.transaction_date
    law_date: date = tx_date if tx_date is not None else date.today()

    return {
        "parsed_receipt": parsed.model_dump(mode="json"),
        "transaction_date": tx_date,
        "law_as_of_date": law_date,
    }


async def _extract_with_gemini(file_path: str) -> ParsedReceipt:
    """Gemini Vision으로 영수증을 파싱한다. 실패 시 fallback을 반환한다."""
    try:
        from tax_copilot.infra.gemini.vision import extract_receipt_fields

        with open(file_path, "rb") as f:
            image_bytes = f.read()

        # 확장자로 MIME 타입 결정
        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
        mime_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "pdf": "application/pdf",
        }
        mime_type = mime_map.get(ext, "image/jpeg")

        return await extract_receipt_fields(image_bytes, mime_type)

    except RuntimeError:
        # API 키 없음 → HITL fallback
        return _fallback_receipt()
    except Exception:
        # Gemini API 오류, 네트워크 오류 등 → HITL fallback
        return _fallback_receipt()
