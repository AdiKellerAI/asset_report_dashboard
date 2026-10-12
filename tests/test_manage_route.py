import io
from datetime import date

from app import create_app
from app.models import Mortgage, Property, TaxReport, Transfer
from app.seed import seed
from tests.test_parsers.conftest import ARCHIVE_DIR, requires_archive


def test_manage_page_renders(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/manage")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Upload New Reports" in body
    assert "Property Values Today" in body
    assert "Yearly Tax Payment" in body
    assert "Transfer to Israel" in body


def test_manage_update_property_values(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()
    colburn = db_session.query(Property).filter_by(nickname="Colburn").one()

    client = create_app().test_client()
    response = client.post(
        "/manage/property-values",
        data={f"value_{brunswick.id}": "96500", f"value_{colburn.id}": "113000"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Property values updated" in response.get_data(as_text=True)

    db_session.refresh(brunswick)
    db_session.refresh(colburn)
    assert float(brunswick.value) == 96500.0
    assert float(colburn.value) == 113000.0


def test_manage_upload_with_no_files_redirects_with_error(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.post("/manage/upload", data={}, content_type="multipart/form-data", follow_redirects=True)

    assert response.status_code == 200
    assert "No files selected" in response.get_data(as_text=True)


@requires_archive
def test_manage_upload_shows_result_popup_with_what_changed(db_session):
    """Adi's feedback (2026-10-12): a plain "success" message isn't
    reassuring when the Home page looks unchanged - the Manage page should
    show what actually moved (the Accumulated Balance before/after, and
    which property/month got new data) right after a successful upload."""
    seed(db_session)
    filename = "Jan 01, 2025 to Jan 31, 2025.zip"
    data = (ARCHIVE_DIR / filename).read_bytes()

    client = create_app().test_client()
    response = client.post(
        "/manage/upload",
        data={"files": (io.BytesIO(data), filename)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Upload Complete" in body
    assert "New Data Added" in body
    assert "Brunswick" in body
    assert 'id="upload-result-overlay"' in body

    # A second GET without a new upload shouldn't show the popup again -
    # it's popped from the session, one-shot, same as the plain flash message.
    second_visit = client.get("/manage")
    assert 'id="upload-result-overlay"' not in second_visit.get_data(as_text=True)


@requires_archive
def test_manage_reupload_same_file_shows_no_new_data(db_session):
    """Re-uploading a file whose content hash is already known is a no-op
    for the data (dedup, dev-plan.md sec 6) - the popup should say so
    plainly instead of implying something changed."""
    seed(db_session)
    filename = "Jan 01, 2025 to Jan 31, 2025.zip"
    data = (ARCHIVE_DIR / filename).read_bytes()

    client = create_app().test_client()
    client.post(
        "/manage/upload", data={"files": (io.BytesIO(data), filename)}, content_type="multipart/form-data", follow_redirects=True
    )
    response = client.post(
        "/manage/upload", data={"files": (io.BytesIO(data), filename)}, content_type="multipart/form-data", follow_redirects=True
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "No new data" in body


def test_manage_mortgage_creates_then_updates_a_single_combined_row(db_session):
    """One combined mortgage for the whole portfolio (Adi confirmed
    2026-08-23), not one per property."""
    seed(db_session)

    client = create_app().test_client()
    response = client.post(
        "/manage/mortgage",
        data={"lender": "Chase", "monthly_payment": "1200.50", "principal_balance": "150000", "start_date": "2022-01-01"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Mortgage updated" in response.get_data(as_text=True)

    mortgage = db_session.query(Mortgage).one()
    assert mortgage.lender == "Chase"
    assert float(mortgage.monthly_payment) == 1200.50
    assert mortgage.start_date == date(2022, 1, 1)

    # posting again updates the same row, doesn't create a second one
    client.post(
        "/manage/mortgage",
        data={"lender": "Chase", "monthly_payment": "1250.00", "principal_balance": "148000", "start_date": "2022-01-01"},
    )
    assert db_session.query(Mortgage).count() == 1
    db_session.refresh(mortgage)
    assert float(mortgage.monthly_payment) == 1250.00


def test_manage_add_tax_report(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.post(
        "/manage/tax",
        data={"year": "2025", "provider": "VirtueTax", "amount_paid": "540.00", "filed_date": "2026-03-15"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Tax payment for 2025 recorded" in body

    report = db_session.query(TaxReport).filter_by(year=2025).one()
    assert float(report.amount_paid) == 540.00
    assert report.filed_date == date(2026, 3, 15)


def test_manage_add_tax_report_requires_a_year(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.post("/manage/tax", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert "needs a valid year" in response.get_data(as_text=True)


def test_manage_add_transfer_uses_month_precision(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.post(
        "/manage/transfer",
        data={"transfer_month": "2026-03", "amount_sent": "2000", "fee": "30", "note": "first in a while"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "recorded" in response.get_data(as_text=True)

    transfer = db_session.query(Transfer).one()
    assert transfer.transfer_date == date(2026, 3, 1)
    assert float(transfer.amount_sent) == 2000.0
    assert float(transfer.fee) == 30.0
    assert transfer.note == "first in a while"


def test_manage_add_transfer_requires_a_month(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.post("/manage/transfer", data={"amount_sent": "100"}, follow_redirects=True)

    assert response.status_code == 200
    assert "needs a month/year" in response.get_data(as_text=True)
