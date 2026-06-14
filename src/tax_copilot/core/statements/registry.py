"""카드사 → 파서 매핑 레지스트리.

각 카드사 파서 모듈은 import 시 register_parser()로 전역 레지스트리에 등록된다.
ingest 파이프라인/API는 get_parser(card_company)로 파서를 꺼내 쓴다.
"""

from __future__ import annotations

from tax_copilot.core.exceptions import ValidationError
from tax_copilot.core.statements.base import StatementParser


class StatementParserRegistry:
    """카드사 식별자로 파서를 등록/조회하는 레지스트리."""

    def __init__(self) -> None:
        self._parsers: dict[str, StatementParser] = {}

    def register(self, parser: StatementParser) -> None:
        self._parsers[parser.card_company] = parser

    def get(self, card_company: str) -> StatementParser:
        parser = self._parsers.get(card_company)
        if parser is None:
            known = ", ".join(sorted(self._parsers)) or "(없음)"
            raise ValidationError(
                f"지원하지 않는 카드사입니다: '{card_company}'. 등록된 카드사: {known}"
            )
        return parser

    def detect(self, filename: str, header: list[str]) -> StatementParser | None:
        """파일명/헤더로 처리 가능한 파서를 자동 판별한다. 없으면 None."""
        for parser in self._parsers.values():
            if parser.matches(filename, header):
                return parser
        return None

    def card_companies(self) -> list[str]:
        return sorted(self._parsers)


# 전역 레지스트리 — 카드사 파서 모듈이 import 시 자기 자신을 등록한다.
_REGISTRY = StatementParserRegistry()


def register_parser(parser: StatementParser) -> None:
    _REGISTRY.register(parser)


def get_parser(card_company: str) -> StatementParser:
    return _REGISTRY.get(card_company)


def detect_parser(filename: str, header: list[str]) -> StatementParser | None:
    return _REGISTRY.detect(filename, header)


def registered_card_companies() -> list[str]:
    return _REGISTRY.card_companies()
