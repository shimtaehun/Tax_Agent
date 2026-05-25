"""세액 계산 노드.

결정론적 Python 함수로 계산한다. LLM이 숫자를 직접 계산하는 일은 없다.
"""

from tax_copilot.agents.state import AgentState
from tax_copilot.agents.tools.vat import calculate_vat_from_supply_value


async def calculation_node(state: AgentState) -> dict:
    """parsed_receipt의 공급가액으로 VAT를 검증 계산한다."""
    parsed = state.get("parsed_receipt") or {}
    supply_value = parsed.get("supply_value_krw")

    if supply_value is None:
        # 공급가액 정보 없음 → 계산 불가, HITL로 넘김
        return {
            "calculation_result": None,
        }

    result = calculate_vat_from_supply_value(supply_value_krw=int(supply_value))
    return {"calculation_result": result}
