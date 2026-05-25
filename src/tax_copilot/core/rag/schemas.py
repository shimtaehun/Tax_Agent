"""법령 chunk 도메인 모델.

core/ 레이어이므로 외부 라이브러리 없음 (pydantic 허용).
Qdrant, Gemini 등 infra 레이어 import 금지.
"""

from datetime import date

from pydantic import BaseModel, field_validator


class LawChunk(BaseModel):
    """법령 조문 단위 chunk.

    chunk_id 형식: {법령약어}-{시행일YYYYMMDD}-art{조번호}-p{항번호}-{해시8자리}
    예: vat-20240101-art39-p1-7f3a9c1a
    """

    chunk_id: str
    law_id: str
    law_name: str
    article_no: str
    paragraph_no: str | None = None
    content: str

    # 시점 정보 — 거래일 기준 검색에 사용
    effective_from: date
    effective_to: date | None = None  # None이면 현행(is_current=True)
    is_current: bool = True

    # 메타데이터
    source_url: str | None = None
    content_hash: str
    corpus_version: str

    @field_validator("effective_from", mode="before")
    @classmethod
    def parse_date(cls, v: object) -> object:
        """ISO 문자열도 date로 변환한다."""
        if isinstance(v, str):
            return date.fromisoformat(v)
        return v

    def is_valid_as_of(self, as_of_date: date) -> bool:
        """거래일 기준으로 이 chunk가 유효한지 확인한다."""
        if self.effective_from > as_of_date:
            return False
        if self.effective_to is not None and self.effective_to <= as_of_date:
            return False
        return True
