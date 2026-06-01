"""RAG 코퍼스 텍스트 chunk 분할 유틸리티."""

from __future__ import annotations

import re


def split_text(text: str, *, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    """긴 본문을 검색용 chunk로 분할한다.

    XML 원문은 조문/결정문처럼 문단 경계가 중요하므로 줄 단위 경계를 우선한다.
    """
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    if len(normalized) <= max_chars:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + max_chars, len(normalized))
        if end < len(normalized):
            boundary = max(
                normalized.rfind(". ", start, end),
                normalized.rfind("다. ", start, end),
                normalized.rfind("요. ", start, end),
                normalized.rfind(" ", start + max_chars // 2, end),
            )
            if boundary > start:
                end = boundary + 1
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap, 0)
    return chunks
