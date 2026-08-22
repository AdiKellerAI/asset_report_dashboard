"""Upload ingestion pipeline (dev-plan.md sec 6): unzip, hash-dedupe, detect,
parse, write to Postgres, flag anything uncertain for the review queue.
"""

import hashlib
import io
import re
import zipfile
from datetime import datetime
from pathlib import Path

import pdfplumber

from app.models import Document, ExpenseType, MonthlyStatement, Property, Transaction, UploadBatch
from app.parsers.owner_packet import categorize_transaction, parse_owner_packet
from app.parsers.sewer_bill import parse_sewer_bill
from app.parsers.signatures import OWNER_PACKET, SEWER_BILL, WATER_BILL, detect_document_type
from app.parsers.water_bill import parse_water_bill
from app.storage import save_document_file

PERIOD_RE = re.compile(r"([A-Za-z]{3})\s+(\d{1,2}),\s+(\d{4})\s+to\s+([A-Za-z]{3})\s+(\d{1,2}),\s+(\d{4})")


def parse_statement_period(filename: str):
    """Derive the statement period from the file's own name (dev-plan.md sec
    3.1) - e.g. "Apr 01, 2022 to Apr 30, 2022.zip" -> (date(2022,4,1), date(2022,4,30)).
    Returns None if the filename doesn't match (e.g. an ad-hoc single bill upload)."""
    match = PERIOD_RE.search(filename)
    if not match:
        return None
    mon1, day1, year1, mon2, day2, year2 = match.groups()
    try:
        start = datetime.strptime(f"{mon1} {day1} {year1}", "%b %d %Y").date()
        end = datetime.strptime(f"{mon2} {day2} {year2}", "%b %d %Y").date()
    except ValueError:
        return None
    return start, end


def _expand_to_raw_files(filename: str, data: bytes):
    """A zip expands to its members; anything else passes through as-is."""
    if filename.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                yield name, zf.read(name)
    else:
        yield filename, data


def process_upload(uploaded_files, session):
    """uploaded_files: list of (filename, bytes) as received from the upload
    request (or read from disk for bulk/local ingestion). Returns the created
    UploadBatch. Idempotent: a file whose content hash already has a Document
    row (from any previous batch) is skipped entirely, not reprocessed."""
    if len(uploaded_files) == 1 and uploaded_files[0][0].lower().endswith(".zip"):
        source = "zip"
    elif len(uploaded_files) == 1:
        source = "single_file"
    else:
        source = "multi_file"

    batch = UploadBatch(source=source, file_count=0)
    session.add(batch)
    session.flush()

    properties_by_nickname = {p.nickname: p for p in session.query(Property).all()}
    expense_types_by_code = {e.code: e for e in session.query(ExpenseType).all()}

    seen_hashes_this_batch = set()
    ingested_count = 0
    skipped_duplicate = 0
    skipped_already_known = 0

    for original_filename, data in uploaded_files:
        period = parse_statement_period(original_filename)

        for member_name, raw in _expand_to_raw_files(original_filename, data):
            digest = hashlib.sha256(raw).hexdigest()

            if digest in seen_hashes_this_batch:
                skipped_duplicate += 1  # bill_*/work_order_* byte-identical overlap
                continue
            seen_hashes_this_batch.add(digest)

            if session.query(Document).filter_by(content_hash=digest).first() is not None:
                skipped_already_known += 1  # already ingested in a previous batch
                continue

            _ingest_one_file(
                member_name, raw, digest, period, batch, session, properties_by_nickname, expense_types_by_code
            )
            ingested_count += 1

    batch.file_count = ingested_count
    notes = []
    if skipped_duplicate:
        notes.append(f"{skipped_duplicate} duplicate file(s) skipped within this batch")
    if skipped_already_known:
        notes.append(f"{skipped_already_known} file(s) already ingested previously")
    batch.notes = "; ".join(notes) or None

    session.commit()
    return batch


def _ingest_one_file(filename, raw, digest, period, batch, session, properties_by_nickname, expense_types_by_code):
    extension = Path(filename).suffix.lower()
    text = _extract_text(raw, extension)
    doc_type = detect_document_type(text) if text else "unknown"

    storage_path = save_document_file(digest, extension, raw)

    document = Document(
        type=doc_type,
        original_filename=filename,
        source_batch_id=batch.id,
        storage_path=storage_path,
        content_hash=digest,
        status="needs_review",
    )
    session.add(document)
    session.flush()

    if doc_type == OWNER_PACKET:
        _ingest_owner_packet(raw, period, document, session, properties_by_nickname, expense_types_by_code)
    elif doc_type in (WATER_BILL, SEWER_BILL):
        _ingest_utility_bill(raw, doc_type, document, properties_by_nickname)
    # unknown: stays needs_review, no further extraction - a human decides


def _extract_text(raw, extension):
    if extension != ".pdf":
        return None  # image files (.jpeg/.jpg) need OCR - not built yet, falls to needs_review
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:  # noqa: BLE001 - a corrupt/unreadable PDF is a review-queue case, not a crash
        return None


def _ingest_owner_packet(raw, period, document, session, properties_by_nickname, expense_types_by_code):
    summaries = parse_owner_packet(io.BytesIO(raw))
    if not summaries or period is None:
        return  # stays needs_review - can't attribute to a property/month

    month = period[0].replace(day=1)
    all_matched = True

    for summary in summaries:
        prop = properties_by_nickname.get(summary.property_nickname)
        if prop is None:
            all_matched = False
            continue

        _upsert_monthly_statement(prop, month, summary, document, session)
        _write_transactions(prop, summary, document, session, expense_types_by_code)

    if all_matched:
        document.status = "parsed"


def _upsert_monthly_statement(prop, month, summary, document, session):
    f = summary.fields
    existing = (
        session.query(MonthlyStatement).filter_by(property_id=prop.id, month=month).one_or_none()
    )
    target = existing or MonthlyStatement(property_id=prop.id, month=month)

    target.beginning_balance = f.get("beginning_balance")
    target.ending_balance = f.get("ending_cash_balance")
    target.unpaid_bills = f.get("unpaid_bills")
    target.reserve = f.get("property_reserve")
    target.net_owner_funds = f.get("net_owner_funds")
    target.source_document_id = document.id
    # gross_income/total_operating_expense/noi are derived from the categorized
    # transaction log (below), not the raw cash_in/cash_out here - those include
    # non-operating cash movements (security deposit transfers, JE entries) that
    # would overstate both. See docs/formats/owner-packet.md.

    if existing is None:
        session.add(target)
    session.flush()


def _write_transactions(prop, summary, document, session, expense_types_by_code):
    # Clear any previously written transactions for this exact document+property
    # (reprocessing the same document should replace, not duplicate).
    session.query(Transaction).filter_by(source_document_id=document.id, property_id=prop.id).delete()

    income_total = 0.0
    expense_total = 0.0

    for txn in summary.transactions:
        code = categorize_transaction(txn.description)
        expense_type = expense_types_by_code.get(code) or expense_types_by_code["other_expense"]
        # amount is always a positive magnitude - income vs. expense is purely
        # determined by expense_type.is_income, not the sign of this column.
        amount = txn.cash_in if txn.cash_in is not None else (txn.cash_out or 0)

        session.add(
            Transaction(
                property_id=prop.id,
                expense_type_id=expense_type.id,
                date=txn.txn_date,
                amount=amount,
                description=txn.description,
                source_document_id=document.id,
            )
        )

        if expense_type.is_income:
            income_total += txn.cash_in or 0
        else:
            expense_total += txn.cash_out or 0

    month_statement = (
        session.query(MonthlyStatement)
        .filter_by(property_id=prop.id, source_document_id=document.id)
        .one_or_none()
    )
    if month_statement is not None:
        month_statement.gross_income = income_total
        month_statement.total_operating_expense = expense_total
        month_statement.noi = income_total - expense_total


def _ingest_utility_bill(raw, doc_type, document, properties_by_nickname):
    bill = parse_water_bill(io.BytesIO(raw)) if doc_type == WATER_BILL else parse_sewer_bill(io.BytesIO(raw))

    prop = properties_by_nickname.get(bill.property_nickname)
    if prop is not None:
        document.property_id = prop.id

    if bill.total_amount_due is not None and prop is not None:
        document.status = "parsed"
    # else: stays needs_review - couldn't attribute amount and/or property
