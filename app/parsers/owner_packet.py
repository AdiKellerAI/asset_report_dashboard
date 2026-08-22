"""Owner Packet.pdf parser (docs/formats/owner-packet.md).

Extracts, per property page: the cash-summary header fields (the numbers that
feed monthly_statement) and the transaction log (the rows that feed
transaction). The statement month is NOT parsed from the PDF - callers derive
it from the zip/file's own filename (dev-plan.md sec 3.1), which is the
documented authoritative source, since in-page date text wraps unreliably
across a line break in some samples.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

import pdfplumber

from app.parsers.common import match_property_nickname, parse_amount

CASH_SUMMARY_FIELD_MAP = {
    "Beginning Balance": "beginning_balance",
    "Cash In": "cash_in",
    "Cash Out": "cash_out",
    "Owner Disbursements": "owner_disbursements",
    "Ending Cash Balance": "ending_cash_balance",
    "Unpaid Bills": "unpaid_bills",
    "Property Reserve": "property_reserve",
    "Net Owner Funds": "net_owner_funds",
    "Please Remit Balance Due": "please_remit_balance_due",
}

# Order matters - more specific keywords first. Anything unmatched falls to
# other_expense, which is a deliberate catch-all category (dev-plan.md sec 4),
# not a parsing failure.
CATEGORY_KEYWORDS = [
    ("rent_income", ["rent income"]),
    ("management_fee", ["management fee"]),
    ("tenant_placement_fee", ["tenant placement", "leasing fee"]),
    ("property_tax", ["property tax"]),
    ("annual_state_fee", ["rental registration"]),
    ("legal_professional_fee", ["legal", "professional fee"]),
    ("maintenance_repair", ["general maintenance", "maintenance labor", "repair"]),
    ("sewer_bill", ["sewer"]),
    ("water_bill", ["water"]),
    ("insurance", ["insurance"]),
    ("tax_prep_fee", ["virtuetax", "tax prep"]),
]


@dataclass
class TransactionRow:
    txn_date: date
    payee: str
    type: str
    reference: str
    description: str
    cash_in: float | None
    cash_out: float | None
    balance: float | None


@dataclass
class PropertyCashSummary:
    property_label: str
    property_nickname: str | None
    fields: dict = field(default_factory=dict)
    transactions: list[TransactionRow] = field(default_factory=list)


def categorize_transaction(description: str) -> str:
    lowered = (description or "").lower()
    for code, keywords in CATEGORY_KEYWORDS:
        if any(kw in lowered for kw in keywords):
            return code
    return "other_expense"


def _parse_cash_summary_fields(table):
    fields = {}
    for row in table:
        if not row or len(row) < 2:
            continue
        key = CASH_SUMMARY_FIELD_MAP.get(row[0])
        if key:
            fields[key] = parse_amount(row[1])
    return fields


def _parse_transactions_table(table):
    transactions = []
    for row in table[1:]:  # skip header row
        if not row:
            continue
        try:
            txn_date = datetime.strptime((row[0] or "").strip(), "%m/%d/%Y").date()
        except ValueError:
            continue  # "Beginning/Ending Cash Balance" marker rows, "Total ..." rows

        def cell(i):
            return (row[i] or "").replace("\n", " ").strip() if i < len(row) else ""

        transactions.append(
            TransactionRow(
                txn_date=txn_date,
                payee=cell(1),
                type=cell(2),
                reference=cell(3),
                description=cell(4),
                cash_in=parse_amount(row[5]) if len(row) > 5 else None,
                cash_out=parse_amount(row[6]) if len(row) > 6 else None,
                balance=parse_amount(row[7]) if len(row) > 7 else None,
            )
        )
    return transactions


def parse_owner_packet(pdf_path, known_nicknames=("Brunswick", "Colburn")):
    """Return a PropertyCashSummary per "Property Cash Summary" page found."""
    summaries = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")
            if "Property Cash Summary" not in lines:
                continue

            idx = lines.index("Property Cash Summary")
            property_label = lines[idx - 1] if idx > 0 else ""
            nickname = match_property_nickname(property_label, known_nicknames)

            tables = page.extract_tables()
            if not tables:
                continue

            fields = _parse_cash_summary_fields(tables[0])
            # Reports before Apr 2022 use a structurally different, older layout
            # (no Beginning/Ending Cash Balance / Net Owner Funds block in the
            # expected position) - not supported yet, skip rather than return
            # garbage. See docs/formats/owner-packet.md.
            if "ending_cash_balance" not in fields or "net_owner_funds" not in fields:
                continue

            transactions = _parse_transactions_table(tables[1]) if len(tables) > 1 else []

            summaries.append(
                PropertyCashSummary(
                    property_label=property_label,
                    property_nickname=nickname,
                    fields=fields,
                    transactions=transactions,
                )
            )
    return summaries
