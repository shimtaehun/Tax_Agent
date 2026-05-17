from collections.abc import Callable, Sequence
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from tax_copilot.core.rag import LawChunk

QDRANT_COLLECTION = "tax_laws"
EMBEDDING_DIM = 768


def build_qdrant_point(chunk: LawChunk, vector: list[float]) -> dict[str, Any]:
    if len(vector) != EMBEDDING_DIM:
        raise ValueError(f"Expected embedding dimension {EMBEDDING_DIM}, got {len(vector)}")

    return {
        "id": str(uuid5(NAMESPACE_URL, chunk.chunk_id)),
        "vector": vector,
        "payload": {
            "chunk_id": chunk.chunk_id,
            "law_id": chunk.law_id,
            "law_mst": chunk.law_mst,
            "law_name": chunk.law_name,
            "article_no": chunk.article_no,
            "paragraph_no": chunk.paragraph_no,
            "subparagraph_no": chunk.subparagraph_no,
            "content": chunk.content,
            "effective_from": chunk.effective_from.isoformat(),
            "effective_to": chunk.effective_to.isoformat() if chunk.effective_to else None,
            "promulgation_date": (
                chunk.promulgation_date.isoformat() if chunk.promulgation_date else None
            ),
            "source_url": chunk.source_url,
            "references": chunk.references,
            "content_hash": chunk.content_hash,
            "corpus_version": chunk.corpus_version,
            "is_current": chunk.effective_to is None,
        },
    }


def upsert_law_chunks(
    client: Any,
    chunks: Sequence[LawChunk],
    embed: Callable[[LawChunk], list[float]],
    *,
    collection_name: str = QDRANT_COLLECTION,
) -> None:
    try:
        from qdrant_client import models
    except ModuleNotFoundError as e:
        message = "qdrant-client is not installed. Run pip-sync requirements/dev.txt."
        raise RuntimeError(message) from e

    points = [models.PointStruct(**build_qdrant_point(chunk, embed(chunk))) for chunk in chunks]
    client.upsert(collection_name=collection_name, points=points)
