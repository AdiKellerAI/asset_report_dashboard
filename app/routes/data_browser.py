"""An elegant, read-only view over every Postgres table - lets Adi sanity-
check the raw data behind the dashboard without opening psql. Swipe left/
right between tables on mobile (base.html's touch handler); rows lazy-load
via infinite scroll (a JSON endpoint + IntersectionObserver in the page's
own script) rather than dumping potentially hundreds of rows at once.
"""

from flask import Blueprint, g, jsonify, render_template, request
from sqlalchemy.orm import joinedload

from app.cache import get_or_set
from app.db import SessionLocal
from app.fx import format_money
from app.i18n import translate
from app.models import (
    Document,
    ExpenseType,
    MonthlyStatement,
    MortgagePayment,
    Property,
    TaxReport,
    Transaction,
    Transfer,
    UploadBatch,
)

data_browser_bp = Blueprint("data_browser", __name__)

PAGE_SIZE = 40


def _date(value):
    return value.isoformat() if value else "—"


def _datetime(value):
    return value.strftime("%Y-%m-%d %H:%M") if value else "—"


def _money(value):
    return format_money(value, g.currency) if value is not None else "—"


def _property_label(prop):
    return prop.nickname if prop else "—"


def _table_configs():
    """Built per-call (not module-level) since column renderers close over
    `g.currency` for money formatting, and `g` only exists during a request."""
    return {
        "property": {
            "label": "Properties",
            "model": Property,
            "order_by": Property.nickname,
            "columns": [
                ("ID", lambda r: r.id),
                ("Nickname", lambda r: r.nickname),
                ("Address", lambda r: r.address or "—"),
                ("Unit Details", lambda r: r.unit_details or "—"),
                ("Purchase Info", lambda r: r.purchase_info or "—"),
                ("Created", lambda r: _datetime(r.created_at)),
            ],
        },
        "expense_type": {
            "label": "Expense Types",
            "model": ExpenseType,
            "order_by": ExpenseType.code,
            "columns": [
                ("ID", lambda r: r.id),
                ("Code", lambda r: r.code),
                ("Label", lambda r: r.label),
                ("Income?", lambda r: "✓" if r.is_income else "—"),
                ("Operating?", lambda r: "✓" if r.is_operating else "—"),
                ("Created", lambda r: _datetime(r.created_at)),
            ],
        },
        "upload_batch": {
            "label": "Upload Batches",
            "model": UploadBatch,
            "order_by": UploadBatch.uploaded_at.desc(),
            "columns": [
                ("ID", lambda r: r.id),
                ("Uploaded", lambda r: _datetime(r.uploaded_at)),
                ("Source", lambda r: r.source),
                ("Files", lambda r: r.file_count),
                ("Notes", lambda r: r.notes or "—"),
            ],
        },
        "document": {
            "label": "Documents",
            "model": Document,
            "order_by": Document.created_at.desc(),
            "eager": [Document.property],
            "columns": [
                ("ID", lambda r: r.id),
                ("Property", lambda r: _property_label(r.property)),
                ("Type", lambda r: r.type),
                ("Filename", lambda r: r.original_filename),
                ("Status", lambda r: r.status),
                ("Uploaded", lambda r: _datetime(r.upload_date)),
            ],
        },
        "transaction": {
            "label": "Transactions",
            "model": Transaction,
            "order_by": Transaction.date.desc(),
            "eager": [Transaction.property, Transaction.expense_type],
            "columns": [
                ("ID", lambda r: r.id),
                ("Property", lambda r: _property_label(r.property)),
                ("Category", lambda r: r.expense_type.label if r.expense_type else "—"),
                ("Date", lambda r: _date(r.date)),
                ("Amount", lambda r: _money(r.amount)),
                ("Description", lambda r: r.description or "—"),
            ],
        },
        "monthly_statement": {
            "label": "Monthly Statements",
            "model": MonthlyStatement,
            "order_by": MonthlyStatement.month.desc(),
            "eager": [MonthlyStatement.property],
            "columns": [
                ("ID", lambda r: r.id),
                ("Property", lambda r: _property_label(r.property)),
                ("Month", lambda r: r.month.strftime("%B %Y") if r.month else "—"),
                ("Gross Income", lambda r: _money(r.gross_income) if r.gross_income is not None else "—"),
                ("NOI", lambda r: _money(r.noi) if r.noi is not None else "—"),
                (
                    "Net Owner Funds",
                    lambda r: _money(r.net_owner_funds) if r.net_owner_funds is not None else "—",
                ),
            ],
        },
        "mortgage": {
            # Every month of the actual combined amortization schedule
            # (Adi's request, 2026-08-26: "show all months from 2021 till
            # the end") - not the single current-snapshot `mortgage` row,
            # which is edited separately via /manage. Just the one combined
            # monthly amount, no principal/interest/balance breakdown (Adi's
            # request, 2026-08-26 - see MortgagePayment's docstring).
            "label": "Mortgage",
            "model": MortgagePayment,
            "order_by": MortgagePayment.month,
            "columns": [
                ("ID", lambda r: r.id),
                ("Date", lambda r: r.month.strftime("%Y-%m") if r.month else "—"),
                ("Amount", lambda r: _money(r.amount)),
            ],
        },
        "tax_report": {
            "label": "Tax Payments",
            "model": TaxReport,
            "order_by": TaxReport.year.desc(),
            "columns": [
                ("ID", lambda r: r.id),
                ("Year", lambda r: r.year),
                ("Provider", lambda r: r.provider),
                ("Amount Paid", lambda r: _money(r.amount_paid) if r.amount_paid is not None else "—"),
                ("Filed Date", lambda r: _date(r.filed_date)),
                ("What It Covers", lambda r: r.what_it_covers or "—"),
            ],
        },
        "transfer": {
            "label": "Transfers",
            "model": Transfer,
            "order_by": Transfer.transfer_date.desc(),
            "columns": [
                ("ID", lambda r: r.id),
                ("Month", lambda r: r.transfer_date.strftime("%B %Y") if r.transfer_date else "—"),
                ("Amount Sent", lambda r: _money(r.amount_sent)),
                ("Fee", lambda r: _money(r.fee)),
                ("Note", lambda r: r.note or "—"),
            ],
        },
    }


def _fetch_page(table_name, offset, limit):
    # Cached as a whole (not just the count) - keyed on currency too, since
    # the Amount/etc. cells are pre-formatted strings (via _money(), which
    # bakes in g.currency at fetch time) rather than raw numbers formatted
    # later by a template filter, unlike the dashboard/trends pages.
    return get_or_set(("table_page", table_name, offset, limit, g.currency), lambda: _fetch_page_uncached(table_name, offset, limit))


def _fetch_page_uncached(table_name, offset, limit):
    config = _table_configs()[table_name]
    session = SessionLocal()
    try:
        total = session.query(config["model"]).count()
        query = session.query(config["model"])
        # Without this, a table whose columns render a relationship (e.g.
        # Transaction's Property/Category) lazy-loads it ONE ROW AT A TIME -
        # 40 rows meant 80 extra Neon round trips, invisible until
        # Transactions became the default table (a real, measured
        # contributor to "the site is very very slow", 2026-08-25).
        for relationship in config.get("eager", []):
            query = query.options(joinedload(relationship))
        rows = query.order_by(config["order_by"]).offset(offset).limit(limit).all()
        headers = [label for label, _ in config["columns"]]
        cells = [[render(row) for _, render in config["columns"]] for row in rows]
    finally:
        session.close()
    return headers, cells, total


DEFAULT_TABLE = "transaction"


@data_browser_bp.get("/tables")
def tables_page():
    configs = _table_configs()
    table_names = list(configs.keys())
    selected = request.args.get("table", DEFAULT_TABLE)
    if selected not in configs:
        selected = DEFAULT_TABLE

    headers, cells, total = _fetch_page(selected, 0, PAGE_SIZE)

    return render_template(
        "tables.html",
        table_names=table_names,
        table_labels={name: cfg["label"] for name, cfg in configs.items()},
        # Pre-translated for the JS-driven prev/next buttons and <select>
        # options, which bypass the `t` Jinja filter (client-side table
        # switching swaps this text in directly, without a fresh render).
        table_labels_translated={name: translate(cfg["label"], g.lang) for name, cfg in configs.items()},
        selected=selected,
        headers=headers,
        rows=cells,
        total=total,
        page_size=PAGE_SIZE,
    )


@data_browser_bp.get("/tables/<table_name>/rows")
def table_rows(table_name):
    configs = _table_configs()
    if table_name not in configs:
        return jsonify(error="unknown table"), 404

    try:
        offset = int(request.args.get("offset", 0))
        limit = min(int(request.args.get("limit", PAGE_SIZE)), 200)
    except ValueError:
        return jsonify(error="invalid offset/limit"), 400

    headers, cells, total = _fetch_page(table_name, offset, limit)
    return jsonify(rows=cells, headers=headers, has_more=offset + len(cells) < total, total=total)
