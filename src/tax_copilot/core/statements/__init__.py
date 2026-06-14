"""카드사 결제내역(엑셀) 파싱·적재 도메인.

패키지 import 시 카드사 파서들을 로드해 전역 레지스트리에 등록한다.
"""

from tax_copilot.core.statements import parsers as parsers  # noqa: F401
