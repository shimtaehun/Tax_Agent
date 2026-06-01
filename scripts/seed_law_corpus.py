"""법령 RAG 코퍼스 시드 스크립트.

기본 실행은 법제처 Open API에서 현행법령, 국세청 법령해석, 조세심판원
특별행정심판례를 수집해 Qdrant에 업로드한다.

실행 예:
  python scripts/seed_law_corpus.py --reset-collection
  python scripts/seed_law_corpus.py --dry-run --law-name 부가가치세법 --query 세금계산서
"""

import argparse
import asyncio
import hashlib
import sys
from datetime import date
from pathlib import Path

# src/ 레이아웃 지원
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tax_copilot.core.rag.schemas import LawChunk
from tax_copilot.infra.gemini.embedding import embed_documents
from tax_copilot.infra.law_open_data import (
    DEFAULT_LAW_NAMES,
    DEFAULT_SEARCH_QUERIES,
    LawOpenDataClient,
    build_law_chunks,
)
from tax_copilot.infra.vector.qdrant import (
    ensure_collection,
    get_client,
    recreate_collection,
    reset_client,
    upsert_chunks,
)

# ──────────────────────────────────────────────────────────────────────────────
# 샘플 법령 데이터 (부가가치세법 주요 조항)
# 실제 서비스에서는 law.go.kr API로 수집
# ──────────────────────────────────────────────────────────────────────────────
_CORPUS_VERSION = "phase3-v1"

RAW_CHUNKS = [
    {
        "law_id": "vat",
        "law_name": "부가가치세법",
        "article_no": "제38조",
        "paragraph_no": "제1항",
        "content": (
            "매입세액은 다음 각 호의 것으로 한다. "
            "1. 사업자가 자기의 사업을 위하여 사용하였거나 사용할 목적으로 공급받은 재화 또는 용역에 대한 세금계산서의 매입세액"  # noqa: E501
        ),
        "effective_from": date(2014, 1, 1),
        "effective_to": None,
        "is_current": True,
        "source_url": "https://www.law.go.kr/법령/부가가치세법/제38조",
    },
    {
        "law_id": "vat",
        "law_name": "부가가치세법",
        "article_no": "제39조",
        "paragraph_no": "제1항",
        "content": (
            "다음 각 호의 매입세액은 매출세액에서 공제하지 아니한다. "
            "1. 세금계산서를 받지 아니한 경우 또는 받은 세금계산서에 필요적 기재사항의 전부 또는 일부가 적혀 있지 아니하거나 "  # noqa: E501
            "사실과 다르게 적혀 있는 경우의 매입세액"
        ),
        "effective_from": date(2014, 1, 1),
        "effective_to": None,
        "is_current": True,
        "source_url": "https://www.law.go.kr/법령/부가가치세법/제39조",
    },
    {
        "law_id": "vat",
        "law_name": "부가가치세법",
        "article_no": "제46조",
        "paragraph_no": "제1항",
        "content": (
            "신용카드등의 사용에 따른 세액공제: 사업자가 대통령령으로 정하는 신용카드등으로 재화 또는 용역을 공급한 경우에는 "  # noqa: E501
            "그 대금을 신용카드등으로 결제받은 금액의 100분의 1.3에 해당하는 금액을 납부할 세액에서 공제한다."  # noqa: E501
        ),
        "effective_from": date(2023, 1, 1),
        "effective_to": None,
        "is_current": True,
        "source_url": "https://www.law.go.kr/법령/부가가치세법/제46조",
    },
    {
        "law_id": "cit",
        "law_name": "법인세법",
        "article_no": "제25조",
        "paragraph_no": "제1항",
        "content": (
            "접대비는 각 사업연도에 지출한 접대비 중 다음 각 호의 금액의 합계액을 한도로 손금에 산입한다. "  # noqa: E501
            "1. 1천200만원(중소기업의 경우에는 2천400만원). "
            "2. 수입금액에 다음 각 목의 구분에 따른 율을 곱하여 산출한 금액."
        ),
        "effective_from": date(2019, 1, 1),
        "effective_to": None,
        "is_current": True,
        "source_url": "https://www.law.go.kr/법령/법인세법/제25조",
    },
    {
        "law_id": "cit",
        "law_name": "법인세법",
        "article_no": "제27조",
        "paragraph_no": "제1항",
        "content": (
            "다음 각 호의 금액은 각 사업연도의 소득금액을 계산할 때 손금에 산입하지 아니한다. "
            "1. 자본거래 등으로 인한 손실의 금액. "
            "2. 제25조에 따른 접대비로서 같은 조에 따라 계산한 한도액을 초과하는 금액."
        ),
        "effective_from": date(2014, 1, 1),
        "effective_to": None,
        "is_current": True,
        "source_url": "https://www.law.go.kr/법령/법인세법/제27조",
    },
]


def _make_chunk_id(law_id: str, article_no: str, paragraph_no: str | None, content: str) -> str:
    """chunk_id를 생성한다."""
    art_slug = article_no.replace("제", "art").replace("조", "")
    para_slug = f"-p{paragraph_no.replace('제', '').replace('항', '')}" if paragraph_no else ""
    hash8 = hashlib.sha256(content.encode()).hexdigest()[:8]
    return f"{law_id}-{art_slug}{para_slug}-{hash8}"


def build_sample_chunks() -> list[LawChunk]:
    """RAW_CHUNKS에서 LawChunk 목록을 생성한다."""
    chunks = []
    for raw in RAW_CHUNKS:
        content = raw["content"]
        chunk_id = _make_chunk_id(
            raw["law_id"], raw["article_no"], raw.get("paragraph_no"), content
        )
        chunks.append(
            LawChunk(
                chunk_id=chunk_id,
                law_id=raw["law_id"],
                law_name=raw["law_name"],
                article_no=raw["article_no"],
                paragraph_no=raw.get("paragraph_no"),
                content=content,
                effective_from=raw["effective_from"],
                effective_to=raw.get("effective_to"),
                is_current=raw.get("is_current", True),
                source_url=raw.get("source_url"),
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
                corpus_version=_CORPUS_VERSION,
            )
        )
    return chunks


def collect_law_api_chunks(args: argparse.Namespace) -> list[LawChunk]:
    """법제처 API에서 RAG chunk를 수집한다."""
    client = LawOpenDataClient()
    corpus_version = f"law-api-{date.today().strftime('%Y%m%d')}"
    documents = []
    law_names = args.law_name or list(DEFAULT_LAW_NAMES)
    queries = args.query or list(DEFAULT_SEARCH_QUERIES)

    if not args.skip_laws:
        documents.extend(client.fetch_current_laws(law_names))
    if not args.skip_interpretations:
        documents.extend(
            client.fetch_nts_interpretations(
                queries,
                max_pages=args.max_pages,
                display=args.display,
            )
        )
    if not args.skip_tribunal:
        documents.extend(
            client.fetch_tax_tribunal_cases(
                queries,
                max_pages=args.max_pages,
                display=args.display,
            )
        )

    return build_law_chunks(documents, corpus_version=corpus_version, max_chars=args.max_chars)


async def main(args: argparse.Namespace) -> None:
    reset_client()

    if args.source == "sample":
        chunks = build_sample_chunks()
    else:
        chunks = collect_law_api_chunks(args)

    if args.limit_chunks is not None:
        chunks = chunks[: args.limit_chunks]
    print(f"수집된 chunk: {len(chunks)}개")
    if not chunks:
        raise SystemExit("수집된 법령 chunk가 없습니다. 검색어/페이지 설정을 확인하세요.")
    if args.dry_run:
        for chunk in chunks[:5]:
            print(f"- {chunk.law_name} {chunk.article_no}: {chunk.content[:120]}")
        return

    print(f"임베딩 중... ({len(chunks)}개 chunk)")

    texts = [chunk.content for chunk in chunks]
    vectors = await embed_documents(texts)

    client = get_client(in_memory=args.in_memory, url=args.qdrant_url)
    if args.reset_collection:
        recreate_collection(client)
    else:
        ensure_collection(client)

    upsert_chunks(client, chunks, vectors)
    print(f"Qdrant에 {len(chunks)}개 chunk 업로드 완료.")
    print(f"corpus_version: {chunks[0].corpus_version}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("law-api", "sample"), default="law-api")
    parser.add_argument("--in-memory", action="store_true")
    parser.add_argument("--qdrant-url", default=None)
    parser.add_argument("--reset-collection", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--law-name", action="append", default=None)
    parser.add_argument("--query", action="append", default=None)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--display", type=int, default=20)
    parser.add_argument("--max-chars", type=int, default=1200)
    parser.add_argument("--limit-chunks", type=int, default=None)
    parser.add_argument("--skip-laws", action="store_true")
    parser.add_argument("--skip-interpretations", action="store_true")
    parser.add_argument("--skip-tribunal", action="store_true")
    args = parser.parse_args()

    asyncio.run(main(args))
