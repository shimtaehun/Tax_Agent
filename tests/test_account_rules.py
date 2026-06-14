"""거래처별 계정과목 학습 규칙 매칭 테스트."""

from tax_copilot.core.tax.account_rules import MerchantRule, match_account_rule


def _rule(pattern: str, code: str, match_type: str = "contains") -> MerchantRule:
    return MerchantRule(match_type=match_type, pattern=pattern, account_code=code)  # type: ignore[arg-type]


def test_no_merchant_returns_none() -> None:
    assert match_account_rule(None, [_rule("스타벅스", "복리후생비")]) is None


def test_contains_match() -> None:
    result = match_account_rule("스타벅스 강남점", [_rule("스타벅스", "복리후생비")])
    assert result is not None
    code, reason = result
    assert code == "복리후생비"
    assert "스타벅스" in reason


def test_exact_takes_priority_over_contains() -> None:
    rules = [
        _rule("스타벅스", "소모품비", match_type="contains"),
        _rule("스타벅스", "복리후생비", match_type="exact"),
    ]
    result = match_account_rule("스타벅스", rules)
    assert result is not None
    code, reason = result
    assert code == "복리후생비"
    assert "완전일치" in reason


def test_exact_does_not_match_substring() -> None:
    result = match_account_rule("스타벅스 강남점", [_rule("스타벅스", "복리후생비", "exact")])
    assert result is None


def test_no_match_returns_none() -> None:
    assert match_account_rule("이디야", [_rule("스타벅스", "복리후생비")]) is None


def test_case_insensitive() -> None:
    result = match_account_rule("STARBUCKS Seoul", [_rule("starbucks", "복리후생비")])
    assert result is not None
    assert result[0] == "복리후생비"
