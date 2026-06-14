"""Qdrant 벡터 검색 어댑터.

컬렉션 구조:
  tax_laws  — 법령 본문 (부가가치세법, 법인세법 등 조문)
  tax_cases — 심판례 · 해석례 (tax-tribunal, nts-interpretation)

검색 전략: tax_laws 우선 검색 → 결과 부족 시 tax_cases 보완.
"""

from __future__ import annotations

from datetime import date

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

COLLECTION_NAME = "tax_laws"
CASES_COLLECTION = "tax_cases"
EMBEDDING_DIM = 1024

_CASE_SOURCE_IDS = {"tax-tribunal", "nts-interpretation"}

_client: QdrantClient | None = None


def get_client(*, in_memory: bool = False, url: str | None = None) -> QdrantClient:
    global _client
    if _client is None:
        if in_memory:
            _client = QdrantClient(":memory:")
        else:
            from tax_copilot.core.config import settings

            _client = QdrantClient(url=url or settings.qdrant_url)
    return _client


def reset_client() -> None:
    global _client
    _client = None


def _create_collection(client: QdrantClient, name: str) -> None:
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        hnsw_config=HnswConfigDiff(m=16, ef_construct=100),
    )


def ensure_collection(client: QdrantClient) -> None:
    """두 컬렉션이 없으면 생성한다."""
    existing = {c.name for c in client.get_collections().collections}
    for name in (COLLECTION_NAME, CASES_COLLECTION):
        if name not in existing:
            _create_collection(client, name)


def recreate_collection(client: QdrantClient) -> None:
    """두 컬렉션을 삭제하고 다시 생성한다."""
    existing = {c.name for c in client.get_collections().collections}
    for name in (COLLECTION_NAME, CASES_COLLECTION):
        if name in existing:
            client.delete_collection(collection_name=name)
        _create_collection(client, name)


def upsert_chunks(
    client: QdrantClient,
    chunks: list[LawChunk],
    vectors: list[list[float]],
    batch_size: int = 200,
) -> None:
    """법령 chunk를 law_id 기준으로 tax_laws / tax_cases에 분리 저장한다."""
    ensure_collection(client)

    _NO_EXPIRY = 99991231

    law_points: list[PointStruct] = []
    case_points: list[PointStruct] = []

    for chunk, vector in zip(chunks, vectors, strict=True):
        point = PointStruct(
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
        if chunk.law_id in _CASE_SOURCE_IDS:
            case_points.append(point)
        else:
            law_points.append(point)

    for collection, points in ((COLLECTION_NAME, law_points), (CASES_COLLECTION, case_points)):
        for i in range(0, len(points), batch_size):
            client.upsert(collection_name=collection, points=points[i : i + batch_size])

    print(f"  법령 본문: {len(law_points)}건 → {COLLECTION_NAME}")
    print(f"  심판례/해석례: {len(case_points)}건 → {CASES_COLLECTION}")


def _query_collection(
    client: QdrantClient,
    collection: str,
    query_vector: list[float],
    as_of_date: date,
    top_k: int,
    score_threshold: float,
) -> list[dict]:
    as_of_int = float(int(as_of_date.strftime("%Y%m%d")))
    must = [FieldCondition(key="effective_from_int", range=Range(lte=as_of_int))]
    should = [
        FieldCondition(key="effective_to_int", range=Range(gt=as_of_int)),
        FieldCondition(key="is_current", match=MatchValue(value=True)),
    ]
    response = client.query_points(
        collection_name=collection,
        query=query_vector,
        query_filter=Filter(must=must, should=should),
        limit=top_k,
        with_payload=True,
    )
    return [
        {**hit.payload, "score": hit.score}
        for hit in response.points
        if hit.payload is not None and hit.score >= score_threshold
    ]


def search_by_date(
    client: QdrantClient,
    query_vector: list[float],
    as_of_date: date,
    top_k: int = 3,
    score_threshold: float = 0.45,
) -> list[dict]:
    """법령 본문 우선 검색. 결과가 부족하면 심판례로 보완한다."""
    results = _query_collection(
        client, COLLECTION_NAME, query_vector, as_of_date, top_k, score_threshold
    )

    if len(results) < 2:
        cases = _query_collection(
            client,
            CASES_COLLECTION,
            query_vector,
            as_of_date,
            top_k - len(results),
            score_threshold,
        )
        results = results + cases

    return results
