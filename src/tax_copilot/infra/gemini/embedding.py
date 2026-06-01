"""Gemini 임베딩 어댑터.

gemini-embedding-2 모델 사용. API 키 없으면 함수 호출 시 예외 발생.
쿼리와 문서에 각각 다른 prefix를 붙인다 (모델 권장 방식).
"""

from tax_copilot.core.config import settings

_MODEL = "gemini-embedding-2"
_DIM = 3072

_QUERY_PREFIX = "query: "
_DOC_PREFIX = "passage: "


def _get_client():  # type: ignore[return]
    """google-genai 클라이언트를 반환한다. API 키가 없으면 RuntimeError."""
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
    from google import genai

    return genai.Client(api_key=settings.gemini_api_key)


async def embed_query(text: str) -> list[float]:
    """검색 쿼리를 벡터로 변환한다."""
    client = _get_client()
    result = client.models.embed_content(
        model=_MODEL,
        contents=_QUERY_PREFIX + text,
    )
    return result.embeddings[0].values


async def embed_documents(texts: list[str]) -> list[list[float]]:
    """법령 chunk 목록을 벡터로 변환한다.

    Gemini embed_content에 리스트를 넘기면 임베딩을 1개만 반환하므로
    텍스트별로 개별 호출한다.
    """
    client = _get_client()
    vectors = []
    for text in texts:
        result = client.models.embed_content(
            model=_MODEL,
            contents=_DOC_PREFIX + text,
        )
        vectors.append(result.embeddings[0].values)
    return vectors
