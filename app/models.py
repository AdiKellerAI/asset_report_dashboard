from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Property(Base):
    __tablename__ = "property"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nickname: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    unit_details: Mapped[str | None] = mapped_column(Text)
    purchase_info: Mapped[str | None] = mapped_column(Text)
    # Purchase price in USD - the denominator for the Annual Yield chart
    # (annual NOI / value). Manually entered via /manage, not parsed from
    # any document. Column kept as `value` (not renamed to purchase_price)
    # to avoid churning every existing reference to it - "Purchase Price"
    # is a UI label, not a schema concern.
    value: Mapped[float | None] = mapped_column(Numeric(12, 2))
    # Auto-fetched current market value estimate (RentCast's AVM API, by
    # address) - Adi's request, 2026-08-27: show today's value next to the
    # purchase price on /manage. Refreshed lazily (on a /manage visit, not
    # a background job - this app has no scheduler) when stale; see
    # app/valuation.py. Purely informational - doesn't feed the Annual
    # Yield chart or any other calculation, only `value` (purchase price)
    # does, unchanged.
    current_value: Mapped[float | None] = mapped_column(Numeric(12, 2))
    current_value_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ExpenseType(Base):
    __tablename__ = "expense_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    is_income: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # False for non-operating cash movements (intra-portfolio transfers, security
    # deposit sweeps, owner distributions/contributions) - excluded from
    # monthly_statement.gross_income/total_operating_expense/noi even though the
    # individual transaction row is still kept for the audit trail.
    is_operating: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UploadBatch(Base):
    __tablename__ = "upload_batch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int | None] = mapped_column(ForeignKey("property.id"))
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    upload_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batch.id"))
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    raw_extracted_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="needs_review")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    property: Mapped["Property | None"] = relationship()
    source_batch: Mapped["UploadBatch | None"] = relationship()


class Transaction(Base):
    __tablename__ = "transaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("property.id"), nullable=False)
    expense_type_id: Mapped[int] = mapped_column(ForeignKey("expense_type.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[int | None] = mapped_column(ForeignKey("document.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    property: Mapped["Property"] = relationship()
    expense_type: Mapped["ExpenseType"] = relationship()
    source_document: Mapped["Document | None"] = relationship()


class MonthlyStatement(Base):
    __tablename__ = "monthly_statement"
    __table_args__ = (UniqueConstraint("property_id", "month", name="uq_monthly_statement_property_month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("property.id"), nullable=False)
    month: Mapped[date] = mapped_column(Date, nullable=False)
    gross_income: Mapped[float | None] = mapped_column(Numeric(12, 2))
    total_operating_expense: Mapped[float | None] = mapped_column(Numeric(12, 2))
    noi: Mapped[float | None] = mapped_column(Numeric(12, 2))
    beginning_balance: Mapped[float | None] = mapped_column(Numeric(12, 2))
    ending_balance: Mapped[float | None] = mapped_column(Numeric(12, 2))
    unpaid_bills: Mapped[float | None] = mapped_column(Numeric(12, 2))
    reserve: Mapped[float | None] = mapped_column(Numeric(12, 2))
    net_owner_funds: Mapped[float | None] = mapped_column(Numeric(12, 2))
    source_document_id: Mapped[int | None] = mapped_column(ForeignKey("document.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    property: Mapped["Property"] = relationship()
    source_document: Mapped["Document | None"] = relationship()


class Mortgage(Base):
    """One combined mortgage for the whole portfolio (Adi confirmed 2026-08-23
    it's a single loan covering both properties, not one per property) -
    portfolio-level like `transfer`, no property_id. Only ever affects the
    Total column of "Net Cash Flow", never an individual property's own column,
    since it isn't attributable to one property alone."""

    __tablename__ = "mortgage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lender: Mapped[str | None] = mapped_column(String(100))
    monthly_payment: Mapped[float | None] = mapped_column(Numeric(12, 2))
    principal_balance: Mapped[float | None] = mapped_column(Numeric(12, 2))
    start_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MortgagePayment(Base):
    """One row per calendar month of the actual combined amortization
    schedule across every loan tranche Discount Bank has ever issued for
    this mortgage (tranches get refinanced/replaced over the years - e.g. one
    tranche closed and was replaced by a new one on 2024-12-29) - portfolio-
    level like `mortgage` itself, not per-property (the mortgage covers both
    assets together, so there's nothing to split). Sourced from Discount
    Bank's own loan-history and forward-amortization statements (manually
    transcribed, like `mortgage` - not run through the automated ingestion
    pipeline), unique on `month` since the combined total across every
    tranche is what's tracked. Just the one combined `amount` per month -
    Adi deliberately doesn't want the principal/interest/remaining-balance
    breakdown carried here (2026-08-26), only the flat monthly total.
    """

    __tablename__ = "mortgage_payment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TaxReport(Base):
    __tablename__ = "tax_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="VirtueTax")
    amount_paid: Mapped[float | None] = mapped_column(Numeric(12, 2))
    what_it_covers: Mapped[str | None] = mapped_column(Text)
    filed_date: Mapped[date | None] = mapped_column(Date)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("document.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document: Mapped["Document | None"] = relationship()


class Transfer(Base):
    """A Wise transfer moving accumulated owner funds from Overland to Israel.

    Portfolio-level (not per-property) since Overland holds combined funds.
    """

    __tablename__ = "transfer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_sent: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    fee: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[int | None] = mapped_column(ForeignKey("document.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    source_document: Mapped["Document | None"] = relationship()
