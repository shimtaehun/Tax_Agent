"""Qdrant 벡터 검색 어댑터.

Phase 3: qdrant-client의 in-memory 모드로 시작.
Phase 5: settings.qdrant_url로 외부 Qdrant 서버 연결.

거래일 기준 필터:
  effective_from <= as_of_date
  AND (effective_to > as_of_date OR is_current = true)
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

from tax_copilot.core.rag.schemas import LawChunk

if TYPE_CHECKING:
    pass

COLLECTION_NAME = "tax_laws"
EMBEDDING_DIM = 768

# 프로세스 단위 싱글턴. 테스트에서는 _reset_client()로 초기화.
_client: QdrantClient | None = None


def get_client(*, in_memory: bool = False, url: str | None = None) -> QdrantClient:
    """QdrantClient 싱글턴을 반환한다."""
    global _client
    if _client is None:
        if in_memory:
            _client = QdrantClient(":memory:")
        else:
            from tax_copilot.core.config import settings

            _client = QdrantClient(url=url or settings.qdrant_url)
    return _client


def reset_client() -> None:
    """테스트 격리를 위해 싱글턴을 초기화한다."""
    global _client
    _client = None


def ensure_collection(client: QdrantClient) -> None:
    """컬렉션이 없으면 생성한다."""
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
            ),
            hnsw_config=HnswConfigDiff(m=16, ef_construct=100),
        )


def upsert_chunks(
    client: QdrantClient,
    chunks: list[LawChunk],
    vectors: list[list[float]],
) -> None:
    """법령 chunk와 임베딩 벡터를 Qdrant에 저장한다."""
    ensure_collection(client)

    # chunk_id를 정수 ID로 변환 (hash 사용)
    # 날짜를 YYYYMMDD 정수로 저장 — Qdrant Range 필터는 숫자만 지원
    _NO_EXPIRY = 99991231  # effective_to=None(현행법) 대용값

    points = [
        PointStruct(
            id=abs(hash(chunk.chunk_id)) % (2**31),
            vector=vector,
            payload={
                "chunk_id": chunk.chunk_id,
                "law_id": chunk.law_id,
                "law_name": chunk.law_name,
                "article_no": chunk.article_no,
                "paragraph_no": chunk.paragraph_no,
                "content": chunk.content,
                "effective_from_int": int(chunk.effective_from.strftime("%Y%m%d")),
                "effective_to_int": (
                    int(chunk.effective_to.strftime("%Y%m%d"))
                    if chunk.effective_to is not None
                    else _NO_EXPIRY
                ),
                "is_current": chunk.is_current,
                "corpus_version": chunk.corpus_version,
                "source_url": chunk.source_url,
                "content_hash": chunk.content_hash,
            },
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)


def search_by_date(
    client: QdrantClient,
    query_vector: list[float],
    as_of_date: date,
    top_k: int = 5,
) -> list[dict]:
    """거래일 기준 법령 chunk를 검색한다.

    필터 조건:
      effective_from <= as_of_date
      AND (effective_to > as_of_date OR is_current = true)
    """
    # YYYYMMDD 정수로 비교
    as_of_int = float(int(as_of_date.strftime("%Y%m%d")))

    # effective_from_int <= as_of_date
    must = [
        FieldCondition(
            key="effective_from_int",
            range=Range(lte=as_of_int),
        )
    ]

    # effective_to_int > as_of_date (현행법은 99991231로 저장되어 항상 통과)
    should = [
        FieldCondition(
            key="effective_to_int",
            range=Range(gt=as_of_int),
        ),
        FieldCondition(
            key="is_current",
            match=MatchValue(value=True),
        ),
    ]

    # qdrant-client 1.12+: search() → query_points()
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=Filter(must=must, should=should),
        limit=top_k,
        with_payload=True,
    )

    return [
        {
            **hit.payload,
            "score": hit.score,
        }
        for hit in response.points
        if hit.payload is not None
    ]
