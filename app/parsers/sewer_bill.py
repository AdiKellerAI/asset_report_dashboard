"""Northeast Ohio Regional Sewer District bill parser (docs/formats/sewer-bill.md).

Regex-based, using only the labeled itemized breakdown (Fixed/Sewage/Stormwater
Charge + TOTAL AMOUNT DUE) - the compact unlabeled summary row pdfplumber
extracts near the top isn't reliably attributable to specific columns, see the
format note.
"""

import re
from dataclasses import dataclass

import pdfplumber

from app.parsers.common import match_property_nickname, parse_amount

ACCOUNT_RE = re.compile(r"ACCOUNT:\s*(\S+)")
SERVICE_ADDRESS_RE = re.compile(r"SERVICE ADDRESS:\s*(.+)")
BILLING_DATE_RE = re.compile(r"BILLING DATE:\s*(\d{2}/\d{2}/\d{4})")
DUE_DATE_RE = re.compile(r"DUE DATE:\s*(\d{2}/\d{2}/\d{4})")
FIXED_CHARGE_RE = re.compile(r"Fixed Charge - (\d{2}-\d{2}-\d{4}) to (\d{2}-\d{2}-\d{4})\s+\$?([\d,]+\.\d{2})")
SEWAGE_CHARGE_RE = re.compile(r"Sewage Charge.*?\$?([\d,]+\.\d{2})\s*$", re.MULTILINE)
STORMWATER_CHARGE_RE = re.compile(r"Stormwater Charge.*?\$?([\d,]+\.\d{2})\s*$", re.MULTILINE)
TOTAL_AMOUNT_DUE_RE = re.compile(r"TOTAL AMOUNT DUE\s+\$?([\d,]+\.\d{2})")


@dataclass
class SewerBill:
    account: str | None
    service_address: str | None
    property_nickname: str | None
    billing_date: str | None
    due_date: str | None
    fixed_charge_period: tuple[str, str] | None
    fixed_charge_amount: float | None
    sewage_charge: float | None
    stormwater_charge: float | None
    total_amount_due: float | None


def parse_sewer_bill(pdf_path, known_nicknames=("Brunswick", "Colburn")):
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    service_address_match = SERVICE_ADDRESS_RE.search(text)
    service_address = service_address_match.group(1).strip() if service_address_match else None
    fixed_charge_match = FIXED_CHARGE_RE.search(text)

    return SewerBill(
        account=_group(ACCOUNT_RE, text),
        service_address=service_address,
        property_nickname=match_property_nickname(service_address, known_nicknames),
        billing_date=_group(BILLING_DATE_RE, text),
        due_date=_group(DUE_DATE_RE, text),
        fixed_charge_period=(fixed_charge_match.group(1), fixed_charge_match.group(2))
        if fixed_charge_match
        else None,
        fixed_charge_amount=parse_amount(fixed_charge_match.group(3)) if fixed_charge_match else None,
        sewage_charge=parse_amount(_group(SEWAGE_CHARGE_RE, text)),
        stormwater_charge=parse_amount(_group(STORMWATER_CHARGE_RE, text)),
        total_amount_due=parse_amount(_group(TOTAL_AMOUNT_DUE_RE, text)),
    )


def _group(pattern, text):
    match = pattern.search(text)
    return match.group(1).strip() if match else None
