"""카드사 결제내역 파서 플러그인 프로토콜.

카드사마다 엑셀 컬럼/형식이 달라서, 각 카드사 파서를 이 프로토콜에 맞춰
구현하고 registry에 등록한다. 새 카드사 추가는 독립 작업으로 병렬화 가능.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from tax_copilot.core.statements.schemas import StatementRow


@runtime_checkable
class StatementParser(Protocol):
    """카드사 엑셀 결제목록 파서가 구현해야 하는 인터페이스."""

    #: 카드사 식별자 (예: "shinhan", "samsung"). registry 키로 쓰인다.
    card_company: str

    def matches(self, filename: str, header: list[str]) -> bool:
        """이 파서가 해당 파일(파일명/헤더 행)을 처리할 수 있으면 True.

        카드사를 명시하지 않은 업로드에서 자동 판별에 쓴다.
        """
        ...

    def parse(self, filename: str, content: bytes) -> list[StatementRow]:
        """엑셀 바이트를 정규화된 StatementRow 리스트로 변환한다."""
        ...
