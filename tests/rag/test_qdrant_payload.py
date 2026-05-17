import importlib.util

import pytest

from tax_copilot.core.rag import DEFAULT_TAX_LAW_CORPUS
from tax_copilot.infra.rag import (
    EMBEDDING_DIM,
    QDRANT_COLLECTION,
    build_qdrant_point,
    upsert_law_chunks,
)


def test_build_qdrant_point_payload_preserves_versioning_fields() -> None:
    chunk = DEFAULT_TAX_LAW_CORPUS[0]
    point = build_qdrant_point(chunk, [0.0] * EMBEDDING_DIM)

    assert isinstance(point["id"], str)
    assert point["payload"]["effective_from"] == chunk.effective_from.isoformat()
    assert point["payload"]["chunk_id"] == chunk.chunk_id
    assert point["payload"]["corpus_version"] == chunk.corpus_version
    assert point["payload"]["content_hash"] == chunk.content_hash


def test_build_qdrant_point_rejects_wrong_embedding_dimension() -> None:
    with pytest.raises(ValueError, match="Expected embedding dimension"):
        build_qdrant_point(DEFAULT_TAX_LAW_CORPUS[0], [0.0])


@pytest.mark.skipif(
    importlib.util.find_spec("qdrant_client") is None,
    reason="qdrant-client missing",
)
def test_upsert_law_chunks_to_in_memory_qdrant() -> None:
    from qdrant_client import QdrantClient, models

    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE),
    )

    def embed(_: object) -> list[float]:
        return [1.0] + [0.0] * (EMBEDDING_DIM - 1)

    upsert_law_chunks(client, DEFAULT_TAX_LAW_CORPUS, embed)

    assert client.count(collection_name=QDRANT_COLLECTION, exact=True).count == 20
