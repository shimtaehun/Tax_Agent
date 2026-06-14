"""가맹점명·증빙 종류 기반 계정과목 규칙 분류기.

LLM 없이 키워드 매칭으로 분류하는 순수 함수. 영수증(audit_prepare 노드)과
카드 결제내역(statements ingest)이 공통으로 재사용한다.
"""

from __future__ import annotations

from tax_copilot.core.tax.schemas import AccountCode

# 가맹점명 키워드 → 계정과목 (우선순위 순)
_MERCHANT_KEYWORD_MAP: list[tuple[list[str], AccountCode]] = [
    (
        [
            "택시",
            "카카오택시",
            "우버",
            "타다",
            "주유",
            "주유소",
            "ktx",
            "srt",
            "버스",
            "지하철",
            "공항",
        ],
        "여비교통비",
    ),
    (
        ["카페", "커피", "스타벅스", "이디야", "투썸", "약국", "의원", "병원", "클리닉"],
        "복리후생비",
    ),
    (
        ["식당", "음식점", "한식", "중식", "일식", "치킨", "피자", "분식", "고기", "삼겹", "갈비"],
        "접대비",
    ),
    (["통신", "skt", "kt", "lgu", "인터넷", "핸드폰"], "통신비"),
    (["서점", "교보문고", "영풍문고", "알라딘", "예스24", "인쇄", "출력"], "도서인쇄비"),
    (["학원", "강의", "교육", "세미나", "훈련", "연수"], "교육훈련비"),
    (["광고", "홍보", "마케팅", "현수막", "배너"], "광고선전비"),
    (["임대", "임차", "월세", "주차"], "임차료"),
    (["보험"], "보험료"),
    (["수리", "수선", "as", "유지보수"], "수선비"),
    (["세금", "공과", "협회비", "회비"], "세금과공과"),
    (["용역", "프리랜서", "외주", "개발", "디자인", "번역"], "외주용역비"),
    (
        [
            "편의점",
            "gs25",
            "cu",
            "세븐일레븐",
            "이마트24",
            "마트",
            "홈플러스",
            "이마트",
            "코스트코",
            "문구",
        ],
        "소모품비",
    ),  # noqa: E501
]

# 증빙 종류별 기본 계정과목 (키워드 매칭 실패 시 fallback)
_DEFAULT_ACCOUNT_BY_EVIDENCE: dict[str, AccountCode] = {
    "tax_invoice": "소모품비",
    "credit_card_slip": "소모품비",
    "cash_receipt": "소모품비",
    "invoice": "소모품비",
    "simplified_receipt": "소모품비",
    "receipt": "소모품비",  # Gemini가 반환하는 일반 영수증 타입
    "simple_receipt": "소모품비",
    "unknown": "미분류",
}


def classify_account_code(
    merchant_name: str | None,
    evidence_type: str,
) -> tuple[AccountCode, str | None]:
    """가맹점명·증빙 종류 기반으로 계정과목을 분류한다.

    반환: (계정과목, 분류 근거 설명). 분류 불가 시 ('미분류', None).
    """
    if merchant_name:
        name_lower = merchant_name.lower()
        for keywords, code in _MERCHANT_KEYWORD_MAP:
            if any(kw.lower() in name_lower for kw in keywords):
                return code, f"가맹점명 '{merchant_name}' 패턴 매칭"

    default = _DEFAULT_ACCOUNT_BY_EVIDENCE.get(evidence_type, "미분류")
    if default == "미분류":
        return "미분류", None
    return default, f"증빙 종류 '{evidence_type}' 기본값"
