import io

from app import create_app
from app.seed import seed


def test_upload_route_processes_a_real_zip(db_session):
    seed(db_session)
    with open(
        "/Users/adikeller/Documents/assets/overland_reports/Jan 01, 2025 to Jan 31, 2025.zip", "rb"
    ) as f:
        data = f.read()

    client = create_app().test_client()
    response = client.post(
        "/upload",
        data={"files": (io.BytesIO(data), "Jan 01, 2025 to Jan 31, 2025.zip")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["source"] == "zip"
    assert body["file_count"] == 3  # Owner Packet + 2 utility bills, no work orders that month


def test_upload_route_requires_files():
    client = create_app().test_client()
    response = client.post("/upload", data={}, content_type="multipart/form-data")

    assert response.status_code == 400
