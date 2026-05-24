"""세무조사 리스크 스코어링 순수 함수.

접대비 비율, 간이영수증 비율, 위험 플래그 비율, 중복 의심 비율을
기반으로 0~100 리스크 점수를 계산한다.
"""

from typing import Any

# 스코어 컴포넌트별 최대 점수 (합계 100)
_MAX_ENTERTAINMENT = 40
_MAX_SIMPLIFIED = 30
_MAX_RISK_FLAG = 20
_MAX_DUPLICATE = 10


def _entertainment_score(ratio: float) -> tuple[int, str | None]:
    """접대비 비율로 스코어 계산 (0~40)."""
    if ratio > 0.30:
        return _MAX_ENTERTAINMENT, f"접대비 비율 {ratio:.0%} — 업종 평균 대비 높음"
    if ratio > 0.15:
        return 25, f"접대비 비율 {ratio:.0%} — 주의 필요"
    if ratio > 0.05:
        return 10, f"접대비 비율 {ratio:.0%}"
    return 0, None


def _simplified_score(ratio: float) -> tuple[int, str | None]:
    """간이영수증 비율로 스코어 계산 (0~30)."""
    if ratio > 0.40:
        return _MAX_SIMPLIFIED, f"간이영수증 비율 {ratio:.0%} — 세금계산서 수취 권장"
    if ratio > 0.20:
        return 15, f"간이영수증 비율 {ratio:.0%}"
    return 0, None


def _risk_flag_score(ratio: float) -> tuple[int, str | None]:
    """위험 플래그 비율로 스코어 계산 (0~20)."""
    if ratio > 0.30:
        return _MAX_RISK_FLAG, f"위험 플래그 비율 {ratio:.0%} — 증빙 검토 필요"
    if ratio > 0.10:
        return 10, f"위험 플래그 비율 {ratio:.0%}"
    return 0, None


def _duplicate_score(ratio: float) -> tuple[int, str | None]:
    """중복 의심 비율로 스코어 계산 (0~10)."""
    if ratio > 0.05:
        return _MAX_DUPLICATE, f"중복 의심 영수증 비율 {ratio:.0%}"
    if ratio > 0:
        return 5, f"중복 의심 영수증 {ratio:.0%}"
    return 0, None


def score_risk(stats: dict[str, Any]) -> dict[str, Any]:
    """영수증 집계 통계에서 세무조사 리스크 점수를 계산한다.

    Args:
        stats: {
            "total_approved": int,
            "total_supply_value_krw": int,
            "entertainment_supply_value_krw": int,
            "simplified_receipt_count": int,
            "risk_flag_count": int,
            "duplicate_suspect_count": int,
        }

    Returns:
        score(0~100), flags(list[str]), explanation(str), indicators(dict) 를 담은 dict.
    """
    total_approved = int(stats.get("total_approved") or 0)
    total_supply = int(stats.get("total_supply_value_krw") or 0)
    entertainment_supply = int(stats.get("entertainment_supply_value_krw") or 0)
    simplified_count = int(stats.get("simplified_receipt_count") or 0)
    risk_flag_count = int(stats.get("risk_flag_count") or 0)
    duplicate_count = int(stats.get("duplicate_suspect_count") or 0)

    if total_approved == 0 or total_supply == 0:
        return {
            "score": 0,
            "flags": [],
            "explanation": "분석할 승인 영수증이 없습니다.",
            "indicators": {
                "entertainment_ratio": 0.0,
                "simplified_ratio": 0.0,
                "risk_flag_ratio": 0.0,
                "duplicate_ratio": 0.0,
            },
        }

    entertainment_ratio = entertainment_supply / total_supply
    simplified_ratio = simplified_count / total_approved
    risk_flag_ratio = risk_flag_count / total_approved
    duplicate_ratio = duplicate_count / total_approved

    e_score, e_flag = _entertainment_score(entertainment_ratio)
    s_score, s_flag = _simplified_score(simplified_ratio)
    r_score, r_flag = _risk_flag_score(risk_flag_ratio)
    d_score, d_flag = _duplicate_score(duplicate_ratio)

    total_score = min(100, e_score + s_score + r_score + d_score)
    flags = [f for f in [e_flag, s_flag, r_flag, d_flag] if f is not None]

    if total_score >= 60:
        summary = "세무조사 리스크가 높습니다."
    elif total_score >= 30:
        summary = "일부 지표에서 주의가 필요합니다."
    else:
        summary = "리스크 지표가 정상 범위입니다."

    explanation = summary + (" " + " / ".join(flags) if flags else "")

    return {
        "score": total_score,
        "flags": flags,
        "explanation": explanation,
        "indicators": {
            "entertainment_ratio": round(entertainment_ratio, 4),
            "simplified_ratio": round(simplified_ratio, 4),
            "risk_flag_ratio": round(risk_flag_ratio, 4),
            "duplicate_ratio": round(duplicate_ratio, 4),
        },
    }
