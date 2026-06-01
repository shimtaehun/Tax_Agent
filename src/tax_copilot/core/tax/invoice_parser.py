"""Parsers for Hometax tax invoice XML/CSV exports."""

from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from typing import Any

from tax_copilot.core.exceptions import ValidationError
from tax_copilot.infra.db.models.tax_invoice import (
    INVOICE_DIRECTION_PURCHASE,
    INVOICE_DIRECTION_SALE,
)

_SALE_WORDS = ("매출", "sale", "sales", "issued")
_PURCHASE_WORDS = ("매입", "purchase", "purchases", "received")


@dataclass(frozen=True)
class ParsedTaxInvoice:
    direction: str
    approval_no: str
    issue_date: date
    supplier_business_no: str | None
    supplier_name: str | None
    recipient_business_no: str | None
    recipient_name: str | None
    item_name: str | None
    supply_value_krw: int
    vat_krw: int
    total_amount_krw: int
    raw_data: dict[str, Any]


def parse_tax_invoice_file(
    filename: str, content: bytes, default_direction: str | None = None
) -> list[ParsedTaxInvoice]:
    """Parse a Hometax XML or CSV export into normalized invoice rows."""
    lower = filename.lower()
    direction = _normalize_direction(default_direction)
    if lower.endswith(".csv"):
        return _parse_csv(content, direction)
    if lower.endswith(".xml"):
        return [_parse_xml(content, direction)]
    raise ValidationError("세금계산서는 XML 또는 CSV 파일만 업로드할 수 있습니다.")


def _parse_csv(content: bytes, default_direction: str | None) -> list[ParsedTaxInvoice]:
    text = _decode_text(content)
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValidationError("CSV 헤더를 찾을 수 없습니다.")

    rows: list[ParsedTaxInvoice] = []
    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue
        rows.append(_invoice_from_mapping(row, default_direction))
    if not rows:
        raise ValidationError("CSV에서 세금계산서 데이터를 찾을 수 없습니다.")
    return rows


def _parse_xml(content: bytes, default_direction: str | None) -> ParsedTaxInvoice:
    lowered = content[:1024].lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ValidationError("외부 엔티티가 포함된 XML은 업로드할 수 없습니다.")
    try:
        root = ET.fromstring(content)  # noqa: S314 - guarded above; no defusedxml dependency.
    except ET.ParseError as exc:
        raise ValidationError("XML 세금계산서 파일을 파싱할 수 없습니다.") from exc

    values: dict[str, str] = {}
    for element in root.iter():
        key = _local_name(element.tag)
        text = (element.text or "").strip()
        if text and key not in values:
            values[key] = text
    return _invoice_from_mapping(values, default_direction)


def _invoice_from_mapping(
    source: dict[str, Any], default_direction: str | None
) -> ParsedTaxInvoice:
    direction = _direction_from_mapping(source) or default_direction
    if direction is None:
        raise ValidationError("매출/매입 구분을 확인할 수 없습니다.")

    approval_no = _first(
        source,
        "승인번호",
        "승인 번호",
        "approval_no",
        "approvalNo",
        "IssueID",
        "issue_id",
        "국세청승인번호",
    )
    if not approval_no:
        raise ValidationError("승인번호가 없는 세금계산서입니다.")

    issue_date_value = _first(source, "작성일자", "발행일자", "issue_date", "IssueDate", "일자")
    issue_date = _parse_date(issue_date_value)
    supply = _parse_int(
        _first(source, "공급가액", "supply_value_krw", "SupplyValue", "ChargeTotalAmount")
    )
    vat = _parse_int(_first(source, "세액", "부가세", "vat_krw", "TaxTotalAmount", "TaxAmount"))
    total = _parse_int(_first(source, "합계금액", "총금액", "total_amount_krw", "GrandTotalAmount"))
    if total == 0:
        total = supply + vat

    return ParsedTaxInvoice(
        direction=direction,
        approval_no=approval_no,
        issue_date=issue_date,
        supplier_business_no=_first(
            source, "공급자등록번호", "supplier_business_no", "InvoicerPartyID"
        ),
        supplier_name=_first(source, "공급자상호", "공급자", "supplier_name", "InvoicerNameText"),
        recipient_business_no=_first(
            source, "공급받는자등록번호", "recipient_business_no", "InvoiceePartyID"
        ),
        recipient_name=_first(
            source, "공급받는자상호", "공급받는자", "recipient_name", "InvoiceeNameText"
        ),
        item_name=_first(source, "품목명", "품목", "item_name", "NameText"),
        supply_value_krw=supply,
        vat_krw=vat,
        total_amount_krw=total,
        raw_data={str(k): v for k, v in source.items()},
    )


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError("CSV 인코딩을 읽을 수 없습니다.")


def _normalize_direction(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {INVOICE_DIRECTION_SALE.lower(), "sales", "매출"}:
        return INVOICE_DIRECTION_SALE
    if normalized in {INVOICE_DIRECTION_PURCHASE.lower(), "purchases", "매입"}:
        return INVOICE_DIRECTION_PURCHASE
    raise ValidationError("invoice_direction은 SALE 또는 PURCHASE이어야 합니다.")


def _direction_from_mapping(source: dict[str, Any]) -> str | None:
    value = _first(source, "구분", "매출매입구분", "direction", "invoice_direction", "type")
    if not value:
        return None
    lower = value.lower()
    if any(word in lower for word in _SALE_WORDS):
        return INVOICE_DIRECTION_SALE
    if any(word in lower for word in _PURCHASE_WORDS):
        return INVOICE_DIRECTION_PURCHASE
    return _normalize_direction(value)


def _first(source: dict[str, Any], *keys: str) -> str | None:
    normalized = {_normalize_key(k): v for k, v in source.items()}
    for key in keys:
        value = normalized.get(_normalize_key(key))
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _normalize_key(key: Any) -> str:
    return str(key).replace(" ", "").replace("_", "").replace("-", "").lower()


def _parse_date(value: str | None) -> date:
    if not value:
        raise ValidationError("작성일자가 없는 세금계산서입니다.")
    cleaned = value.replace(".", "-").replace("/", "-").strip()
    if len(cleaned) == 8 and cleaned.isdigit():
        cleaned = f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:]}"
    try:
        return date.fromisoformat(cleaned[:10])
    except ValueError as exc:
        raise ValidationError("작성일자 형식을 읽을 수 없습니다.") from exc


def _parse_int(value: str | None) -> int:
    if not value:
        return 0
    cleaned = value.replace(",", "").replace("원", "").strip()
    try:
        return int(float(cleaned))
    except ValueError as exc:
        raise ValidationError("금액 형식을 읽을 수 없습니다.") from exc


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
