from datetime import date

from flask import Blueprint, g, redirect, render_template, request, url_for

from app.db import SessionLocal
from app.i18n import translate_message
from app.ingestion import process_upload
from app.models import Document, Mortgage, Property, TaxReport, Transfer

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


@manage_bp.get("/manage")
def manage():
    session = SessionLocal()
    try:
        properties = session.query(Property).order_by(Property.nickname).all()
        mortgages_by_property = {m.property_id: m for m in session.query(Mortgage).all()}
        tax_reports = session.query(TaxReport).order_by(TaxReport.year.desc()).all()
        transfers = session.query(Transfer).order_by(Transfer.transfer_date.desc()).all()
    finally:
        session.close()

    return render_template(
        "manage.html",
        properties=properties,
        mortgages_by_property=mortgages_by_property,
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

    msg = translate_message("Uploaded batch processed: {count} file(s) ingested", g.lang, count=batch.file_count)
    if needs_review:
        msg += translate_message(", {count} need review", g.lang, count=needs_review)
    if batch.notes:
        msg += f" ({batch.notes})"
    return redirect(url_for("manage.manage", msg=msg, level="success"))


@manage_bp.post("/manage/mortgage/<nickname>")
def update_mortgage(nickname):
    session = SessionLocal()
    try:
        prop = session.query(Property).filter_by(nickname=nickname).one_or_none()
        if prop is None:
            return _redirect_with_message("Unknown property {name!r}.", "error", name=nickname)

        mortgage = session.query(Mortgage).filter_by(property_id=prop.id).one_or_none()
        if mortgage is None:
            mortgage = Mortgage(property_id=prop.id)
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

    return _redirect_with_message("Mortgage updated for {name}.", name=nickname)


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

    return _redirect_with_message("Transfer for {when} recorded.", when=transfer_date.strftime("%B %Y"))
