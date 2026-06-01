"""법제처 Open API XML 수집기.

지원 소스:
- 현행법령 본문 XML: lawSearch.do(target=law) + lawService.do(target=law)
- 국세청 법령해석 목록 XML: lawSearch.do(target=ntsCgmExpc)
- 조세심판원 특별행정심판례 목록/본문 XML: lawSearch.do/lawService.do(target=ttSpecialDecc)
"""

from __future__ import annotations

import hashlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET  # noqa: S405
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date

from tax_copilot.core.config import settings
from tax_copilot.core.rag.chunking import split_text
from tax_copilot.core.rag.schemas import LawChunk

LAW_API_BASE_URL = "https://www.law.go.kr/DRF"
DEFAULT_LAW_NAMES = ("부가가치세법", "법인세법", "소득세법", "조세특례제한법")
DEFAULT_SEARCH_QUERIES = ("부가가치세", "세금계산서", "매입세액", "접대비")
_MIN_EFFECTIVE_DATE = date(1900, 1, 1)


@dataclass(frozen=True)
class LawApiDocument:
    """API에서 수집한 원문 문서."""

    source_type: str
    document_id: str
    title: str
    body: str
    published_at: date
    source_url: str
    article_no: str = "본문"


FetchText = Callable[[str, dict[str, str | int]], str]


class LawOpenDataClient:
    """법제처 Open API 클라이언트."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = LAW_API_BASE_URL,
        fetch_text: FetchText | None = None,
    ) -> None:
        self.api_key = api_key or settings.law_api_key
        self.base_url = base_url.rstrip("/")
        self._fetch_text = fetch_text or self._default_fetch_text

    def fetch_current_laws(self, law_names: Iterable[str]) -> list[LawApiDocument]:
        """현행법령 본문 XML을 수집한다."""
        documents: list[LawApiDocument] = []
        for law_name in law_names:
            mst = self._find_law_mst(law_name)
            params: dict[str, str | int] = {"target": "law", "type": "XML"}
            if mst:
                params["MST"] = mst
            else:
                params["LM"] = law_name

            root = self._request_xml("lawService.do", params)
            resolved_name = (
                _first_text(root, ("법령명_한글", "법령명", "한글법령명", "법령명한글")) or law_name
            )
            published_at = _parse_date_text(
                _first_text(root, ("시행일자", "공포일자", "개정문시행일자"))
            )
            source_url = self._build_public_url("lawService.do", params)
            documents.extend(
                _parse_law_article_documents(
                    root,
                    law_name=resolved_name,
                    law_id=mst or _slug(resolved_name),
                    published_at=published_at,
                    source_url=source_url,
                )
            )
        return documents

    def fetch_nts_interpretations(
        self,
        queries: Iterable[str],
        *,
        max_pages: int = 1,
        display: int = 20,
    ) -> list[LawApiDocument]:
        """국세청 법령해석 목록 XML을 수집한다."""
        return self._fetch_search_documents(
            target="ntsCgmExpc",
            source_type="nts-interpretation",
            title_fallback="국세청 법령해석",
            queries=queries,
            max_pages=max_pages,
            display=display,
        )

    def fetch_tax_tribunal_cases(
        self,
        queries: Iterable[str],
        *,
        max_pages: int = 1,
        display: int = 20,
    ) -> list[LawApiDocument]:
        """조세심판원 특별행정심판례 목록 XML과 본문 XML을 수집한다."""
        documents: list[LawApiDocument] = []
        seen_ids: set[str] = set()
        for query in queries:
            for page in range(1, max_pages + 1):
                root = self._request_xml(
                    "lawSearch.do",
                    {
                        "target": "ttSpecialDecc",
                        "type": "XML",
                        "query": query,
                        "page": page,
                        "display": display,
                    },
                )
                for record in _record_elements(root):
                    doc_id = _first_text(
                        record,
                        ("ID", "id", "특별행정심판재결례일련번호", "판례일련번호", "일련번호"),
                    )
                    if not doc_id or doc_id in seen_ids:
                        continue
                    seen_ids.add(doc_id)
                    title = (
                        _first_text(
                            record, ("사건명", "청구번호", "제목", "title", "판례명", "심판례명")
                        )
                        or "조세심판원 특별행정심판례"
                    )
                    list_text = _flatten_text(record)
                    published_at = _parse_date_text(
                        _first_text(record, ("선고일자", "결정일자", "작성일자", "일자"))
                    )
                    body = self._fetch_tribunal_body(doc_id, list_text)
                    source_url = self._build_public_url(
                        "lawService.do",
                        {"target": "ttSpecialDecc", "type": "XML", "ID": doc_id},
                    )
                    documents.append(
                        LawApiDocument(
                            source_type="tax-tribunal",
                            document_id=doc_id,
                            title=title,
                            body=body,
                            published_at=published_at,
                            source_url=source_url,
                        )
                    )
        return documents

    def _fetch_search_documents(
        self,
        *,
        target: str,
        source_type: str,
        title_fallback: str,
        queries: Iterable[str],
        max_pages: int,
        display: int,
    ) -> list[LawApiDocument]:
        documents: list[LawApiDocument] = []
        seen_ids: set[str] = set()
        for query in queries:
            for page in range(1, max_pages + 1):
                root = self._request_xml(
                    "lawSearch.do",
                    {
                        "target": target,
                        "type": "XML",
                        "query": query,
                        "page": page,
                        "display": display,
                    },
                )
                for record in _record_elements(root):
                    body = _flatten_text(record)
                    if not body:
                        continue
                    doc_id = _first_text(record, ("ID", "id", "일련번호", "관리번호", "문서번호"))
                    doc_id = doc_id or hashlib.sha256(body.encode()).hexdigest()[:16]
                    if doc_id in seen_ids:
                        continue
                    seen_ids.add(doc_id)
                    title = _first_text(record, ("안건명", "제목", "title", "문서명"))
                    published_at = _parse_date_text(
                        _first_text(record, ("생산일자", "작성일자", "회신일자", "일자"))
                    )
                    documents.append(
                        LawApiDocument(
                            source_type=source_type,
                            document_id=doc_id,
                            title=title or title_fallback,
                            body=body,
                            published_at=published_at,
                            source_url=self._build_public_url(
                                "lawSearch.do",
                                {
                                    "target": target,
                                    "type": "XML",
                                    "query": query,
                                    "page": page,
                                    "display": display,
                                },
                            ),
                        )
                    )
        return documents

    def _find_law_mst(self, law_name: str) -> str | None:
        root = self._request_xml(
            "lawSearch.do",
            {"target": "law", "type": "XML", "query": law_name, "display": 1},
        )
        for record in _record_elements(root):
            mst = _first_text(record, ("법령일련번호", "MST", "mst", "lawId"))
            if mst:
                return mst
        return _first_text(root, ("법령일련번호", "MST", "mst", "lawId"))

    def _fetch_tribunal_body(self, doc_id: str, fallback: str) -> str:
        try:
            root = self._request_xml(
                "lawService.do",
                {"target": "ttSpecialDecc", "type": "XML", "ID": doc_id},
            )
        except (ET.ParseError, OSError, ValueError):
            return fallback
        body = _flatten_text(root)
        return body or fallback

    def _request_xml(self, path: str, params: dict[str, str | int]) -> ET.Element:
        text = self._fetch_text(path, self._with_auth(params))
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError("안전하지 않은 XML 응답입니다.")
        return ET.fromstring(text)  # noqa: S314

    def _default_fetch_text(self, path: str, params: dict[str, str | int]) -> str:
        url = self._build_url(path, params)
        with urllib.request.urlopen(url, timeout=20) as response:  # noqa: S310
            raw = response.read()
        for encoding in ("utf-8", "euc-kr", "cp949"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _build_url(self, path: str, params: dict[str, str | int]) -> str:
        query = urllib.parse.urlencode(self._with_auth(params), doseq=True)
        return f"{self.base_url}/{path}?{query}"

    def _build_public_url(self, path: str, params: dict[str, str | int]) -> str:
        query = urllib.parse.urlencode(params, doseq=True)
        return f"{self.base_url}/{path}?{query}"

    def _with_auth(self, params: dict[str, str | int]) -> dict[str, str | int]:
        if not self.api_key:
            raise RuntimeError("LAW_API_KEY가 설정되지 않았습니다.")
        return {"OC": self.api_key, **params}


def build_law_chunks(
    documents: Iterable[LawApiDocument],
    *,
    corpus_version: str,
    max_chars: int = 1200,
) -> list[LawChunk]:
    """수집 원문을 LawChunk 목록으로 변환한다."""
    chunks: list[LawChunk] = []
    seen_hashes: set[str] = set()
    for document in documents:
        for index, content in enumerate(split_text(document.body, max_chars=max_chars), start=1):
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            chunk_id = _make_chunk_id(document, index, content_hash)
            chunks.append(
                LawChunk(
                    chunk_id=chunk_id,
                    law_id=document.source_type,
                    law_name=document.title,
                    article_no=document.article_no,
                    paragraph_no=f"chunk-{index}",
                    content=content,
                    effective_from=document.published_at,
                    effective_to=None,
                    is_current=True,
                    source_url=document.source_url,
                    content_hash=content_hash,
                    corpus_version=corpus_version,
                )
            )
    return chunks


def _parse_law_article_documents(
    root: ET.Element,
    *,
    law_name: str,
    law_id: str,
    published_at: date,
    source_url: str,
) -> list[LawApiDocument]:
    article_elements = [
        element
        for element in root.iter()
        if _local_name(element.tag) in {"조문단위", "article"}
        and _first_text(element, ("조문번호", "조번호"))
    ]
    documents: list[LawApiDocument] = []
    for index, article in enumerate(article_elements, start=1):
        text = _article_content(article)
        if not text:
            continue
        article_no = _article_no(article, index)
        article_title = _first_text(article, ("조문제목", "제목"))
        normalized_article_no = f"제{article_no}조" if article_no.isdecimal() else article_no
        if not article_title and re.match(r"^제\d+장\b", text):
            continue
        title = law_name
        if article_title and not text.startswith(normalized_article_no):
            text = f"{normalized_article_no}({article_title}) {text}"
        documents.append(
            LawApiDocument(
                source_type=_slug(law_id),
                document_id=f"{law_id}-{index}",
                title=title,
                body=text,
                published_at=published_at,
                source_url=source_url,
                article_no=normalized_article_no,
            )
        )
    if documents:
        return documents
    fallback = _flatten_text(root)
    return (
        [
            LawApiDocument(
                source_type=_slug(law_id),
                document_id=law_id,
                title=law_name,
                body=fallback,
                published_at=published_at,
                source_url=source_url,
            )
        ]
        if fallback
        else []
    )


def _article_no(article: ET.Element, index: int) -> str:
    number = _first_text(article, ("조문번호", "조번호")) or str(index)
    branch = _first_text(article, ("조문가지번호", "가지번호"))
    if number.isdecimal() and branch and branch.isdecimal() and int(branch) > 0:
        return f"제{number}조의{int(branch)}"
    return number


def _article_content(article: ET.Element) -> str:
    names = {
        "조문내용",
        "항내용",
        "호내용",
        "목내용",
        "내용",
        "articleContent",
    }
    parts = _texts_by_names(article, names)
    if not parts:
        return _flatten_text(article)
    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        normalized = re.sub(r"\s+", " ", part).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return " ".join(deduped)


def _record_elements(root: ET.Element) -> list[ET.Element]:
    candidates: list[ET.Element] = []
    for element in root.iter():
        children = list(element)
        if len(children) < 2:
            continue
        names = {_local_name(child.tag) for child in children}
        if names & {
            "ID",
            "id",
            "특별행정심판재결례일련번호",
            "일련번호",
            "법령일련번호",
            "제목",
            "사건명",
            "청구번호",
            "안건명",
        }:
            candidates.append(element)
    if candidates:
        return candidates
    return [child for child in list(root) if len(list(child)) >= 2]


def _first_text(element: ET.Element, names: Iterable[str]) -> str | None:
    wanted = set(names)
    for child in element.iter():
        if _local_name(child.tag) in wanted:
            text = " ".join(part.strip() for part in child.itertext() if part.strip())
            if text:
                return text
    return None


def _texts_by_names(element: ET.Element, names: Iterable[str]) -> list[str]:
    wanted = set(names)
    texts: list[str] = []
    for child in element.iter():
        if _local_name(child.tag) in wanted:
            text = " ".join(part.strip() for part in child.itertext() if part.strip())
            if text:
                texts.append(text)
    return texts


def _flatten_text(element: ET.Element) -> str:
    text = re.sub(r"\s+", " ", " ".join(part.strip() for part in element.itertext())).strip()
    return _sanitize_text(text)


def _sanitize_text(text: str) -> str:
    return re.sub(r"([?&]OC=)[^&\s]+", r"\1<redacted>", text)


def _parse_date_text(value: str | None) -> date:
    if not value:
        return _MIN_EFFECTIVE_DATE
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 8:
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            return _MIN_EFFECTIVE_DATE
    return _MIN_EFFECTIVE_DATE


def _make_chunk_id(document: LawApiDocument, index: int, content_hash: str) -> str:
    doc_slug = _slug(document.document_id or document.title)
    return f"{document.source_type}-{doc_slug}-{index}-{content_hash[:8]}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣]+", "-", value).strip("-").lower()
    return slug[:80] or "law"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
