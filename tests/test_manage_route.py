from datetime import date

from app import create_app
from app.models import Mortgage, Property, TaxReport, Transfer
from app.seed import seed


def test_manage_page_renders(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.get("/manage")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Upload New Reports" in body
    assert "Mortgage" in body
    assert "Yearly Tax Payment" in body
    assert "Transfer to Israel" in body
    assert "Brunswick" in body
    assert "Colburn" in body


def test_manage_upload_with_no_files_redirects_with_error(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.post("/manage/upload", data={}, content_type="multipart/form-data", follow_redirects=True)

    assert response.status_code == 200
    assert "No files selected" in response.get_data(as_text=True)


def test_manage_mortgage_creates_then_updates(db_session):
    seed(db_session)
    brunswick = db_session.query(Property).filter_by(nickname="Brunswick").one()

    client = create_app().test_client()
    response = client.post(
        "/manage/mortgage/Brunswick",
        data={"lender": "Chase", "monthly_payment": "1200.50", "principal_balance": "150000", "start_date": "2022-01-01"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Mortgage updated for Brunswick" in response.get_data(as_text=True)

    mortgage = db_session.query(Mortgage).filter_by(property_id=brunswick.id).one()
    assert mortgage.lender == "Chase"
    assert float(mortgage.monthly_payment) == 1200.50
    assert mortgage.start_date == date(2022, 1, 1)

    # posting again updates the same row, doesn't create a second one
    client.post(
        "/manage/mortgage/Brunswick",
        data={"lender": "Chase", "monthly_payment": "1250.00", "principal_balance": "148000", "start_date": "2022-01-01"},
    )
    assert db_session.query(Mortgage).filter_by(property_id=brunswick.id).count() == 1
    db_session.refresh(mortgage)
    assert float(mortgage.monthly_payment) == 1250.00


def test_manage_mortgage_unknown_property_redirects_with_error(db_session):
    seed(db_session)

    client = create_app().test_client()
    response = client.post("/manage/mortgage/NotAReal Property", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert "Unknown property" in response.get_data(as_text=True)


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
