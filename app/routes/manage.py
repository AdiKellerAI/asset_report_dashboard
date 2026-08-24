from datetime import date

from flask import Blueprint, g, redirect, render_template, request, url_for

from app.cache import get_or_set, invalidate_all
from app.db import SessionLocal
from app.i18n import translate_message
from app.ingestion import process_upload
from app.models import Document, Mortgage, Property, TaxReport, Transfer
from app.reports import properties_summary

manage_bp = Blueprint("manage", __name__)


def _parse_float(value):
    if not value:
        return None
    return float(value)


def _parse_date(value):
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_month(value):
    """<input type=month> gives "YYYY-MM" - stored as the 1st of that month,
    since a Wise transfer is only tracked to month/year precision."""
    if not value:
        return None
    year_part, month_part = value.split("-")
    return date(int(year_part), int(month_part), 1)


def _redirect_with_message(template, level="success", **kwargs):
    msg = translate_message(template, g.lang, **kwargs)
    return redirect(url_for("manage.manage", msg=msg, level=level))


def _mortgage_dict(mortgage):
    if mortgage is None:
        return None
    return {
        "lender": mortgage.lender,
        "monthly_payment": mortgage.monthly_payment,
        "principal_balance": mortgage.principal_balance,
        "start_date": mortgage.start_date,
    }


def _tax_report_dict(t):
    return {
        "year": t.year,
        "provider": t.provider,
        "amount_paid": t.amount_paid,
        "filed_date": t.filed_date,
        "what_it_covers": t.what_it_covers,
    }


def _transfer_dict(tr):
    return {"amount_sent": tr.amount_sent, "fee": tr.fee, "note": tr.note, "transfer_date": tr.transfer_date}


@manage_bp.get("/manage")
def manage():
    # Plain-dict conversions (not the ORM objects themselves) so these are
    # cacheable via app/cache.py without risking a DetachedInstanceError on
    # a later cache hit, once the fetching session has closed - this page's
    # 4 queries were previously uncached, paying a full Neon round trip on
    # every single visit even though nothing here changes except right after
    # a /manage write (which already calls invalidate_all()).
    session = SessionLocal()
    try:
        properties = get_or_set(("properties_summary",), lambda: properties_summary(session))
        mortgage = get_or_set(
            ("mortgage_summary",),
            lambda: _mortgage_dict(session.query(Mortgage).order_by(Mortgage.id.desc()).first()),
        )
        tax_reports = get_or_set(
            ("tax_reports_summary",),
            lambda: [_tax_report_dict(t) for t in session.query(TaxReport).order_by(TaxReport.year.desc()).all()],
        )
        transfers = get_or_set(
            ("transfers_summary",),
            lambda: [
                _transfer_dict(tr) for tr in session.query(Transfer).order_by(Transfer.transfer_date.desc()).all()
            ],
        )
    finally:
        session.close()

    return render_template(
        "manage.html",
        properties=properties,
        mortgage=mortgage,
        tax_reports=tax_reports,
        transfers=transfers,
        message=request.args.get("msg"),
        message_level=request.args.get("level", "success"),
    )


@manage_bp.post("/manage/upload")
def upload_reports():
    files = [f for f in request.files.getlist("files") if f.filename]
    if not files:
        return _redirect_with_message("No files selected.", "error")

    uploaded_files = [(f.filename, f.read()) for f in files]
    session = SessionLocal()
    try:
        batch = process_upload(uploaded_files, session)
        needs_review = session.query(Document).filter_by(source_batch_id=batch.id, status="needs_review").count()
    finally:
        session.close()
    invalidate_all()

    msg = translate_message("Uploaded batch processed: {count} file(s) ingested", g.lang, count=batch.file_count)
    if needs_review:
        msg += translate_message(", {count} need review", g.lang, count=needs_review)
    if batch.notes:
        msg += f" ({batch.notes})"
    return redirect(url_for("manage.manage", msg=msg, level="success"))


@manage_bp.post("/manage/mortgage")
def update_mortgage():
    """One combined mortgage for the whole portfolio (Adi confirmed
    2026-08-23 it's a single loan covering both properties) - upserts the
    one existing row rather than one per property."""
    session = SessionLocal()
    try:
        mortgage = session.query(Mortgage).order_by(Mortgage.id.desc()).first()
        if mortgage is None:
            mortgage = Mortgage()
            session.add(mortgage)

        try:
            mortgage.lender = request.form.get("lender") or None
            mortgage.monthly_payment = _parse_float(request.form.get("monthly_payment"))
            mortgage.principal_balance = _parse_float(request.form.get("principal_balance"))
            mortgage.start_date = _parse_date(request.form.get("start_date"))
        except ValueError:
            session.rollback()
            return _redirect_with_message("Couldn't save mortgage - check the numbers/date.", "error")

        session.commit()
    finally:
        session.close()
    invalidate_all()

    return _redirect_with_message("Mortgage updated.")


@manage_bp.post("/manage/property-values")
def update_property_values():
    """Per-property value (dev-plan.md's original per-property purchase/loan
    info) - the denominator for the Annual Yield chart. Unlike the mortgage,
    this genuinely varies per property, so it's one form field per property
    rather than a single combined figure."""
    session = SessionLocal()
    try:
        properties = session.query(Property).order_by(Property.nickname).all()
        try:
            for prop in properties:
                prop.value = _parse_float(request.form.get(f"value_{prop.id}"))
        except ValueError:
            session.rollback()
            return _redirect_with_message("Couldn't save property values - check the numbers.", "error")

        session.commit()
    finally:
        session.close()
    invalidate_all()

    return _redirect_with_message("Property values updated.")


@manage_bp.post("/manage/tax")
def add_tax_report():
    try:
        year = int(request.form["year"])
    except (KeyError, ValueError):
        return _redirect_with_message("Tax payment needs a valid year.", "error")

    session = SessionLocal()
    try:
        try:
            session.add(
                TaxReport(
                    year=year,
                    provider=request.form.get("provider") or "VirtueTax",
                    amount_paid=_parse_float(request.form.get("amount_paid")),
                    what_it_covers=request.form.get("what_it_covers") or None,
                    filed_date=_parse_date(request.form.get("filed_date")),
                )
            )
            session.commit()
        except ValueError:
            session.rollback()
            return _redirect_with_message("Couldn't save the tax payment - check the amount/date.", "error")
    finally:
        session.close()
    invalidate_all()

    return _redirect_with_message("Tax payment for {year} recorded.", year=year)


@manage_bp.post("/manage/transfer")
def add_transfer():
    transfer_date = _parse_month(request.form.get("transfer_month"))
    if transfer_date is None:
        return _redirect_with_message("Transfer needs a month/year.", "error")

    session = SessionLocal()
    try:
        try:
            session.add(
                Transfer(
                    transfer_date=transfer_date,
                    amount_sent=_parse_float(request.form.get("amount_sent")) or 0,
                    fee=_parse_float(request.form.get("fee")) or 0,
                    note=request.form.get("note") or None,
                )
            )
            session.commit()
        except ValueError:
            session.rollback()
            return _redirect_with_message("Couldn't save the transfer - check the amount/fee.", "error")
    finally:
        session.close()
    invalidate_all()

    return _redirect_with_message("Transfer for {when} recorded.", when=transfer_date.strftime("%B %Y"))
