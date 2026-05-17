from datetime import date
from hashlib import sha256
from re import findall

from tax_copilot.core.rag.schemas import LawChunk, LawSearchResult

CORPUS_VERSION = "tax-law-mini-2026.1"


def _content_hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()[:12]


def _chunk(
    *,
    slug: str,
    law_id: str,
    law_name: str,
    article_no: str,
    paragraph_no: str,
    content: str,
    effective_from: date,
    effective_to: date | None = None,
) -> LawChunk:
    content_hash = _content_hash(content)
    return LawChunk(
        chunk_id=f"{slug}-{effective_from:%Y%m%d}-art{article_no}-p{paragraph_no}-{content_hash[:6]}",
        law_id=law_id,
        law_name=law_name,
        article_no=article_no,
        paragraph_no=paragraph_no,
        content=content,
        effective_from=effective_from,
        effective_to=effective_to,
        content_hash=content_hash,
        corpus_version=CORPUS_VERSION,
    )


DEFAULT_TAX_LAW_CORPUS: tuple[LawChunk, ...] = (
    _chunk(
        slug="vat",
        law_id="VAT",
        law_name="Value-Added Tax Act",
        article_no="38",
        paragraph_no="1",
        content=(
            "Input VAT may be credited when a taxable business purchase is supported "
            "by proper evidence."
        ),
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="vat",
        law_id="VAT",
        law_name="Value-Added Tax Act",
        article_no="39",
        paragraph_no="1",
        content=(
            "Input VAT is not creditable when the purchase is unrelated to the taxable business."
        ),
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="vat",
        law_id="VAT",
        law_name="Value-Added Tax Act",
        article_no="39",
        paragraph_no="2",
        content=(
            "Passenger vehicle expenses may be restricted unless statutory business-use "
            "conditions apply."
        ),
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="vat",
        law_id="VAT",
        law_name="Value-Added Tax Act",
        article_no="32",
        paragraph_no="1",
        content="A tax invoice is a qualified evidence document for taxable supply transactions.",
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="vat",
        law_id="VAT",
        law_name="Value-Added Tax Act",
        article_no="46",
        paragraph_no="3",
        content="Credit card slips and cash receipts may support input tax credit review.",
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="cit",
        law_id="CIT",
        law_name="Corporate Income Tax Act",
        article_no="19",
        paragraph_no="1",
        content=(
            "Business expenses are deductible when they are ordinary, necessary, and "
            "business related."
        ),
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="cit",
        law_id="CIT",
        law_name="Corporate Income Tax Act",
        article_no="25",
        paragraph_no="1",
        content=(
            "Entertainment expenses require stricter evidence and are subject to deduction limits."
        ),
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="cit",
        law_id="CIT",
        law_name="Corporate Income Tax Act",
        article_no="116",
        paragraph_no="2",
        content="Qualified evidence includes tax invoices, credit card slips, and cash receipts.",
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="cit",
        law_id="CIT",
        law_name="Corporate Income Tax Act",
        article_no="116",
        paragraph_no="3",
        content=(
            "Simplified receipts may be insufficient when qualified evidence is legally required."
        ),
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="vat",
        law_id="VAT",
        law_name="Value-Added Tax Act",
        article_no="39",
        paragraph_no="4",
        content=(
            "Before 2025, meal purchases require business purpose review and qualified evidence."
        ),
        effective_from=date(2024, 1, 1),
        effective_to=date(2025, 1, 1),
    ),
    _chunk(
        slug="vat",
        law_id="VAT",
        law_name="Value-Added Tax Act",
        article_no="39",
        paragraph_no="4",
        content=(
            "From 2025, meal purchases also require participant and purpose records "
            "for safer review."
        ),
        effective_from=date(2025, 1, 1),
    ),
    _chunk(
        slug="cit",
        law_id="CIT",
        law_name="Corporate Income Tax Act",
        article_no="26",
        paragraph_no="1",
        content="Donation expenses are reviewed separately from ordinary operating expenses.",
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="cit",
        law_id="CIT",
        law_name="Corporate Income Tax Act",
        article_no="27",
        paragraph_no="1",
        content="Personal or non-business expenses are excluded from deductible expenses.",
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="vat",
        law_id="VAT",
        law_name="Value-Added Tax Act",
        article_no="29",
        paragraph_no="1",
        content="VAT taxable amount generally includes consideration received for taxable supply.",
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="vat",
        law_id="VAT",
        law_name="Value-Added Tax Act",
        article_no="36",
        paragraph_no="1",
        content="Simplified tax invoice rules apply only to eligible simplified taxable persons.",
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="cit",
        law_id="CIT",
        law_name="Corporate Income Tax Act",
        article_no="60",
        paragraph_no="1",
        content="Corporate tax reporting must preserve books and evidence for later audit review.",
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="vat",
        law_id="VAT",
        law_name="Value-Added Tax Act",
        article_no="57",
        paragraph_no="1",
        content="Taxpayers must keep evidence necessary to verify VAT reporting details.",
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="cit",
        law_id="CIT",
        law_name="Corporate Income Tax Act",
        article_no="112",
        paragraph_no="1",
        content="Accounting books and documentary evidence must be retained for statutory periods.",
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="vat",
        law_id="VAT",
        law_name="Value-Added Tax Act",
        article_no="10",
        paragraph_no="1",
        content="Place and timing of supply affect the taxable period and reporting treatment.",
        effective_from=date(2024, 1, 1),
    ),
    _chunk(
        slug="cit",
        law_id="CIT",
        law_name="Corporate Income Tax Act",
        article_no="40",
        paragraph_no="1",
        content=(
            "Income and expenses are attributed to the business year in which they are confirmed."
        ),
        effective_from=date(2024, 1, 1),
    ),
)


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in findall(r"[A-Za-z0-9가-힣]+", text) if len(token) > 1}


def search_tax_law(
    query: str,
    as_of_date: date,
    *,
    top_k: int = 3,
    corpus: tuple[LawChunk, ...] = DEFAULT_TAX_LAW_CORPUS,
) -> list[LawSearchResult]:
    query_tokens = _tokens(query)
    results: list[LawSearchResult] = []
    for chunk in corpus:
        if not chunk.is_effective_on(as_of_date):
            continue
        chunk_tokens = _tokens(f"{chunk.law_name} {chunk.content}")
        overlap = len(query_tokens & chunk_tokens)
        if overlap == 0:
            continue
        score = overlap / max(len(query_tokens), 1)
        results.append(LawSearchResult(chunk=chunk, score=score))

    return sorted(
        results,
        key=lambda item: (item.score, item.chunk.effective_from, item.chunk.chunk_id),
        reverse=True,
    )[:top_k]
