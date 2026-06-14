"""로컬 임베딩 서버 어댑터.

POST /embed  {"texts": [...]}  →  {"embeddings": [[...], ...]}
KURE-v1 모델, 1024차원.
"""

import httpx

from tax_copilot.core.config import settings


async def embed_query(text: str) -> list[float]:
    """검색 쿼리를 벡터로 변환한다."""
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{settings.embedding_url}/embed",
            json={"texts": [text]},
            timeout=30.0,
        )
        res.raise_for_status()
    return res.json()["embeddings"][0]


async def embed_documents(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """법령 chunk 목록을 벡터로 변환한다. 배치 단위로 나눠서 전송한다."""
    vectors: list[list[float]] = []
    async with httpx.AsyncClient() as client:
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            res = await client.post(
                f"{settings.embedding_url}/embed",
                json={"texts": batch},
                timeout=120.0,
            )
            res.raise_for_status()
            vectors.extend(res.json()["embeddings"])
            print(f"  임베딩 진행: {min(i + batch_size, len(texts))}/{len(texts)}")
    return vectors
