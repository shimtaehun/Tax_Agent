from datetime import date

from pydantic import BaseModel, Field


class LawChunk(BaseModel):
    chunk_id: str
    law_id: str
    law_mst: str | None = None
    law_name: str
    article_no: str | None
    paragraph_no: str | None = None
    subparagraph_no: str | None = None
    content: str
    effective_from: date
    effective_to: date | None = None
    promulgation_date: date | None = None
    source_url: str | None = None
    references: list[str] = Field(default_factory=list)
    content_hash: str
    corpus_version: str

    def is_effective_on(self, as_of_date: date) -> bool:
        if self.effective_from > as_of_date:
            return False
        return self.effective_to is None or self.effective_to > as_of_date


class LawSearchResult(BaseModel):
    chunk: LawChunk
    score: float
