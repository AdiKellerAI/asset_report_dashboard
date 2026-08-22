"""City of Cleveland Division of Water bill parser (docs/formats/water-bill.md).

Regex-based rather than table-based - unlike the Owner Packet, these bills
aren't laid out as bordered tables; fields are "Label: value" lines (sometimes
sharing a physical line with unrelated text from a two-column layout, hence
searching the whole text blob rather than requiring an exact line match).
"""

import re
from dataclasses import dataclass

import pdfplumber

from app.parsers.common import match_property_nickname, parse_amount

ACCOUNT_NUMBER_RE = re.compile(r"Account Number:\s*(\S+)")
SERVICE_ADDRESS_RE = re.compile(r"Service Address:\s*(.+)")
DUE_DATE_RE = re.compile(r"Due Date:\s*([A-Za-z]+ \d{1,2}, \d{4})")
TOTAL_AMOUNT_DUE_RE = re.compile(r"Total Amount Due:\s*\$?([\d,]+\.\d{2})")
CLEVELAND_WATER_TOTAL_RE = re.compile(r"Cleveland Water Total\s+\$?([\d,]+\.\d{2})")
LOCAL_CHARGES_TOTAL_RE = re.compile(r"Local & Other Current Charges Total\s+\$?([\d,]+\.\d{2})")
FIXED_CHARGE_PERIOD_RE = re.compile(r"Fixed Charge - (\d{2}-\d{2}-\d{4}) to (\d{2}-\d{2}-\d{4})")


@dataclass
class WaterBill:
    account_number: str | None
    service_address: str | None
    property_nickname: str | None
    due_date: str | None
    total_amount_due: float | None
    cleveland_water_total: float | None
    local_charges_total: float | None
    fixed_charge_period: tuple[str, str] | None


def parse_water_bill(pdf_path, known_nicknames=("Brunswick", "Colburn")):
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    service_address_match = SERVICE_ADDRESS_RE.search(text)
    service_address = service_address_match.group(1).strip() if service_address_match else None
    fixed_charge_match = FIXED_CHARGE_PERIOD_RE.search(text)

    return WaterBill(
        account_number=_group(ACCOUNT_NUMBER_RE, text),
        service_address=service_address,
        property_nickname=match_property_nickname(service_address, known_nicknames),
        due_date=_group(DUE_DATE_RE, text),
        total_amount_due=parse_amount(_group(TOTAL_AMOUNT_DUE_RE, text)),
        cleveland_water_total=parse_amount(_group(CLEVELAND_WATER_TOTAL_RE, text)),
        local_charges_total=parse_amount(_group(LOCAL_CHARGES_TOTAL_RE, text)),
        fixed_charge_period=(fixed_charge_match.group(1), fixed_charge_match.group(2))
        if fixed_charge_match
        else None,
    )


def _group(pattern, text):
    match = pattern.search(text)
    return match.group(1).strip() if match else None
