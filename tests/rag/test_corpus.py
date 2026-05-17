from datetime import date

from tax_copilot.core.rag import DEFAULT_TAX_LAW_CORPUS, search_tax_law


def test_default_corpus_has_about_twenty_versioned_chunks() -> None:
    assert len(DEFAULT_TAX_LAW_CORPUS) == 20
    assert all(chunk.corpus_version for chunk in DEFAULT_TAX_LAW_CORPUS)
    assert all(str(chunk.effective_from.year) in chunk.chunk_id for chunk in DEFAULT_TAX_LAW_CORPUS)


def test_search_filters_by_transaction_date() -> None:
    before = search_tax_law("meal purchase business purpose", date(2024, 12, 31), top_k=5)
    after = search_tax_law("meal purchase business purpose", date(2025, 1, 1), top_k=5)

    before_ids = {result.chunk.chunk_id for result in before}
    after_ids = {result.chunk.chunk_id for result in after}

    assert any("20240101-art39-p4" in chunk_id for chunk_id in before_ids)
    assert not any("20250101-art39-p4" in chunk_id for chunk_id in before_ids)
    assert any("20250101-art39-p4" in chunk_id for chunk_id in after_ids)
    assert before_ids != after_ids


def test_search_returns_ranked_relevant_results() -> None:
    results = search_tax_law("credit card cash receipt qualified evidence", date(2026, 1, 1))

    assert results
    assert results[0].score >= results[-1].score
    assert any(result.chunk.article_no == "116" for result in results)
