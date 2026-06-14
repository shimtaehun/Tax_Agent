"""계정과목 규칙 기반 분류기 테스트."""

from tax_copilot.core.tax.account_classifier import classify_account_code


def test_merchant_keyword_match_takes_priority() -> None:
    code, reason = classify_account_code("카카오택시", "credit_card_slip")
    assert code == "여비교통비"
    assert reason is not None and "카카오택시" in reason


def test_cafe_maps_to_welfare() -> None:
    code, _ = classify_account_code("스타벅스 강남점", "credit_card_slip")
    assert code == "복리후생비"


def test_falls_back_to_evidence_default_when_no_keyword() -> None:
    code, reason = classify_account_code("이름없는상점", "credit_card_slip")
    assert code == "소모품비"
    assert reason is not None and "credit_card_slip" in reason


def test_unknown_evidence_without_keyword_is_unclassified() -> None:
    code, reason = classify_account_code(None, "unknown")
    assert code == "미분류"
    assert reason is None
