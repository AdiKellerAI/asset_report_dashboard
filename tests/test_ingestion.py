from datetime import date

import pytest

from app.ingestion import (
    _upsert_monthly_statement,
    _write_transactions,
    parse_statement_period,
    process_upload,
    recategorize_transactions,
)
from app.models import Document, ExpenseType, MonthlyStatement, Property, Transaction
from app.parsers.owner_packet import PropertyCashSummary, TransactionRow
from app.seed import seed
from tests.test_parsers.conftest import ARCHIVE_DIR, requires_archive


def test_parse_statement_period():
    assert parse_statement_period("Apr 01, 2022 to Apr 30, 2022.zip") == (
        date(2022, 4, 1),
        date(2022, 4, 30),
    )
    assert parse_statement_period("Aug 01, 2024 to Aug 31, 2024.pdf") == (
        date(2024, 8, 1),
        date(2024, 8, 31),
    )
    assert parse_statement_period("random_photo.jpeg") is None


def _read(filename):
    return (ARCHIVE_DIR / filename).read_bytes()


@requires_archive
def test_zip_upload_dedupes_bill_and_work_order_pairs(db_session):
    """Apr 2022 zip has 5 bill_*/work_order_* byte-identical pairs (docs/formats/
    owner-packet.md) - only 6 documents should be created (Owner Packet + 5
    unique bills), not 11."""
    seed(db_session)
    filename = "Apr 01, 2022 to Apr 30, 2022.zip"

    batch = process_upload([(filename, _read(filename))], db_session)

    assert batch.source == "zip"
    assert batch.file_count == 6
    assert "5 duplicate file(s) skipped" in batch.notes


@requires_archive
def test_owner_packet_writes_monthly_statements_and_transactions(db_session):
    seed(db_session)
    filename = "Jan 01, 2025 to Jan 31, 2025.zip"  # no work orders, simpler month

    process_upload([(filename, _read(filename))], db_session)

    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    statement = (
        db_session.query(MonthlyStatement)
        .filter_by(property_id=brunswick.id, month=date(2025, 1, 1))
        .one()
    )
    assert float(statement.net_owner_funds) == pytest.approx(1240.20)
    assert float(statement.gross_income) == pytest.approx(1378.00)  # the single Rent Income transaction
    assert float(statement.total_operating_expense) == pytest.approx(137.80)

    transactions = db_session.query(Transaction).filter_by(property_id=brunswick.id).all()
    assert len(transactions) == 2  # rent income + management fee
    rent_txn = next(t for t in transactions if t.expense_type.code == "rent_income")
    assert float(rent_txn.amount) == 1378.00


def test_non_operating_transactions_excluded_from_noi(db_session):
    """docs/PROJECT_STATUS.md's other_expense finding: intra-portfolio transfers,
    security-deposit sweeps, and owner distributions are real cash movements
    (still written as Transaction rows) but must not inflate gross_income/
    total_operating_expense/noi."""
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    expense_types = {e.code: e for e in db_session.query(ExpenseType).all()}
    document = Document(
        type="owner_packet",
        original_filename="test.pdf",
        storage_path="unused",
        content_hash="deadbeef" * 8,
    )
    db_session.add(document)
    db_session.flush()

    month = date(2026, 5, 1)
    _upsert_monthly_statement(
        brunswick,
        month,
        PropertyCashSummary(
            property_label="Brunswick",
            property_nickname="Brunswick",
            fields={"beginning_balance": 0, "ending_cash_balance": 1000, "net_owner_funds": 1000},
        ),
        document,
        db_session,
    )

    summary = PropertyCashSummary(
        property_label="Brunswick",
        property_nickname="Brunswick",
        transactions=[
            TransactionRow(date(2026, 5, 1), "Tenant", "Payment", "", "Rent Income", 1000.0, None, None),
            TransactionRow(date(2026, 5, 2), "Overland", "Transfer", "", "Transfer to 2500 Colburn Ave", None, 400.0, None),
            TransactionRow(
                date(2026, 5, 3), "Overland", "JE", "", "Owner Distribution - Owner payment for 05/2026", None, 300.0, None
            ),
        ],
    )
    _write_transactions(brunswick, summary, document, db_session, expense_types)

    statement = (
        db_session.query(MonthlyStatement).filter_by(property_id=brunswick.id, month=month).one()
    )
    assert float(statement.gross_income) == pytest.approx(1000.0)
    assert float(statement.total_operating_expense) == pytest.approx(0.0)
    assert float(statement.noi) == pytest.approx(1000.0)

    # the transfer/distribution rows are still recorded, just not in the NOI math
    non_operating = (
        db_session.query(Transaction)
        .filter_by(property_id=brunswick.id)
        .join(ExpenseType)
        .filter(ExpenseType.is_operating.is_(False))
        .all()
    )
    assert {t.expense_type.code for t in non_operating} == {"internal_transfer", "owner_distribution"}


def test_recategorize_transactions_corrects_already_ingested_data(db_session):
    """The production-data correction path: transactions already written under
    the old categorize_transaction (before internal_transfer/security_deposit_
    transfer/owner_distribution existed) get fixed in place, and the
    monthly_statement totals they feed get recomputed - no PDF re-parse."""
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    other_expense = db_session.query(ExpenseType).filter_by(code="other_expense").one()
    rent_income = db_session.query(ExpenseType).filter_by(code="rent_income").one()

    document = Document(
        type="owner_packet",
        original_filename="test.pdf",
        storage_path="unused",
        content_hash="cafebabe" * 8,
    )
    db_session.add(document)
    db_session.flush()

    month = date(2026, 5, 1)
    db_session.add(
        MonthlyStatement(
            property_id=brunswick.id,
            month=month,
            source_document_id=document.id,
            gross_income=1000,
            total_operating_expense=400,  # wrong: includes the transfer below
            noi=600,
        )
    )
    db_session.add(
        Transaction(
            property_id=brunswick.id,
            expense_type_id=rent_income.id,
            date=month,
            amount=1000,
            description="Rent Income",
            source_document_id=document.id,
        )
    )
    db_session.add(
        Transaction(
            property_id=brunswick.id,
            expense_type_id=other_expense.id,  # mis-categorized, pre-fix
            date=month,
            amount=400,
            description="Transfer to 2500 Colburn Ave",
            source_document_id=document.id,
        )
    )
    db_session.commit()

    recategorized_count = recategorize_transactions(db_session)

    assert recategorized_count == 1
    transfer_txn = (
        db_session.query(Transaction).filter_by(description="Transfer to 2500 Colburn Ave").one()
    )
    assert transfer_txn.expense_type.code == "internal_transfer"

    statement = (
        db_session.query(MonthlyStatement).filter_by(property_id=brunswick.id, month=month).one()
    )
    assert float(statement.gross_income) == pytest.approx(1000.0)
    assert float(statement.total_operating_expense) == pytest.approx(0.0)
    assert float(statement.noi) == pytest.approx(1000.0)

    # idempotent: running it again changes nothing further
    assert recategorize_transactions(db_session) == 0


@requires_archive
def test_reupload_same_zip_is_idempotent(db_session):
    """dev-plan.md sec 6: re-running the same batch always produces the same
    result - no duplicated documents/transactions on a second upload."""
    seed(db_session)
    filename = "Jan 01, 2025 to Jan 31, 2025.zip"
    data = _read(filename)

    first = process_upload([(filename, data)], db_session)
    transaction_count_after_first = db_session.query(Transaction).count()

    second = process_upload([(filename, data)], db_session)

    assert first.file_count > 0
    assert second.file_count == 0
    assert "already ingested previously" in second.notes
    assert db_session.query(Document).count() == first.file_count  # not doubled
    assert db_session.query(Transaction).count() == transaction_count_after_first  # not doubled


@requires_archive
def test_unrecognized_document_goes_to_review_queue(db_session):
    """A gas/insurance/property-tax bill (see report-ingestion skill) doesn't
    match any known signature and must land as needs_review, not be guessed."""
    seed(db_session)
    filename = "Dec 01, 2024 to Dec 31, 2024.zip"

    process_upload([(filename, _read(filename))], db_session)

    unknown_docs = db_session.query(Document).filter_by(type="unknown").all()
    assert unknown_docs
    assert all(d.status == "needs_review" for d in unknown_docs)


@requires_archive
def test_bulk_upload_whole_archive_at_once(db_session):
    """dev-plan.md sec 8 step 5: the actual day-one use case is bulk-importing
    the whole local archive as one multi-file batch, not one file at a time."""
    seed(db_session)
    files = [(p.name, p.read_bytes()) for p in sorted(ARCHIVE_DIR.iterdir()) if p.suffix in (".zip", ".pdf")]

    batch = process_upload(files, db_session)

    assert batch.source == "multi_file"
    assert batch.file_count > 100  # dozens of owner packets + bills + work orders
    # every property/month combination that has a monthly_statement is unique
    statements = db_session.query(MonthlyStatement).all()
    seen = set()
    for s in statements:
        key = (s.property_id, s.month)
        assert key not in seen
        seen.add(key)
    assert len(statements) > 90  # ~2 properties x ~50 supported months
