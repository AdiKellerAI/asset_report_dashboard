import pytest

from app.parsers.owner_packet import categorize_transaction, parse_owner_packet
from app.parsers.signatures import OWNER_PACKET, detect_document_type
from tests.test_parsers.conftest import all_archive_files, owner_packet_path, requires_archive


@requires_archive
def test_detects_owner_packet_signature(tmp_path):
    path = owner_packet_path("Apr 01, 2022 to Apr 30, 2022.zip", tmp_path)
    text = path.read_bytes()  # sanity: file exists and is non-empty
    assert len(text) > 0
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        assert detect_document_type(pdf.pages[1].extract_text()) == OWNER_PACKET


@requires_archive
def test_parses_two_properties_with_correct_nicknames(tmp_path):
    path = owner_packet_path("Apr 01, 2022 to Apr 30, 2022.zip", tmp_path)
    summaries = parse_owner_packet(path)

    assert len(summaries) == 2
    assert {s.property_nickname for s in summaries} == {"Brunswick", "Colburn"}


@requires_archive
def test_2022_brunswick_cash_summary_fields(tmp_path):
    path = owner_packet_path("Apr 01, 2022 to Apr 30, 2022.zip", tmp_path)
    summaries = parse_owner_packet(path)
    brunswick = next(s for s in summaries if s.property_nickname == "Brunswick")

    assert brunswick.fields["beginning_balance"] == 145.89
    assert brunswick.fields["cash_in"] == 1311.00
    assert brunswick.fields["cash_out"] == -845.25
    assert brunswick.fields["ending_cash_balance"] == 611.64
    assert brunswick.fields["unpaid_bills"] == -311.64
    assert brunswick.fields["property_reserve"] == -300.00
    assert brunswick.fields["net_owner_funds"] == 0.00
    assert "owner_disbursements" not in brunswick.fields


@requires_archive
def test_2022_brunswick_transactions_categorized(tmp_path):
    path = owner_packet_path("Apr 01, 2022 to Apr 30, 2022.zip", tmp_path)
    summaries = parse_owner_packet(path)
    brunswick = next(s for s in summaries if s.property_nickname == "Brunswick")

    by_description = {t.description: t for t in brunswick.transactions}
    rent_txns = [t for t in brunswick.transactions if "Rent Income" in t.description]
    assert len(rent_txns) == 2
    assert all(categorize_transaction(t.description) == "rent_income" for t in rent_txns)
    assert rent_txns[0].cash_in == 700.00

    mgmt = next(t for t in brunswick.transactions if "Management Fees" in t.description)
    assert categorize_transaction(mgmt.description) == "management_fee"
    assert mgmt.cash_out == 125.00

    maint = next(t for t in brunswick.transactions if "General Maintenance Labor" in t.description)
    assert categorize_transaction(maint.description) == "maintenance_repair"
    assert maint.cash_out == 720.25


@requires_archive
def test_2023_colburn_owner_disbursements(tmp_path):
    """The confirmed intra-portfolio-transfer edge case from docs/formats/owner-packet.md."""
    path = owner_packet_path("Aug 01, 2023 to Aug 31, 2023.zip", tmp_path)
    summaries = parse_owner_packet(path)
    colburn = next(s for s in summaries if s.property_nickname == "Colburn")

    assert colburn.fields["owner_disbursements"] == -1215.00
    assert "unpaid_bills" not in colburn.fields
    assert colburn.fields["net_owner_funds"] == 0.00


@requires_archive
def test_2023_brunswick_negative_net_owner_funds(tmp_path):
    """The confirmed negative-Net-Owner-Funds edge case (Unpaid Bills exceeded
    cash balance that month). "Please Remit Balance Due" isn't separately
    extracted - it's outside the bordered table pdfplumber captures, and it's
    mathematically redundant with |net_owner_funds| when negative anyway."""
    path = owner_packet_path("Aug 01, 2023 to Aug 31, 2023.zip", tmp_path)
    summaries = parse_owner_packet(path)
    brunswick = next(s for s in summaries if s.property_nickname == "Brunswick")

    assert brunswick.fields["net_owner_funds"] == -1215.27


@requires_archive
@pytest.mark.parametrize(
    "filename",
    [
        "Apr 01, 2022 to Apr 30, 2022.zip",
        "Aug 01, 2023 to Aug 31, 2023.zip",
        "Mar 01, 2024 to Mar 31, 2024.zip",
        "Jan 01, 2025 to Jan 31, 2025.zip",
        "May 01, 2026 to May 31, 2026.zip",
    ],
)
def test_cash_summary_arithmetic_holds(filename, tmp_path):
    """dev-plan.md sec 8.4 cross-check: Ending Cash Balance - |Unpaid Bills or
    Owner Disbursements| - Property Reserve == Net Owner Funds, confirmed across
    every sample in docs/formats/owner-packet.md."""
    path = owner_packet_path(filename, tmp_path)
    summaries = parse_owner_packet(path)

    for summary in summaries:
        f = summary.fields
        # Only Unpaid Bills reduces Net Owner Funds further - Owner Disbursements
        # (when present instead) is already netted into Ending Cash Balance, so
        # subtracting it again would double-count (see docs/formats/owner-packet.md).
        expected = f["ending_cash_balance"] + f.get("unpaid_bills", 0) + f["property_reserve"]
        assert expected == pytest.approx(f["net_owner_funds"], abs=0.01), (
            f"{filename} {summary.property_nickname}: arithmetic mismatch"
        )


# Confirmed pre-Apr-2022 files using a structurally different, older layout
# (no "Property Cash Summary" field block in the expected position) - not
# supported by this parser yet, see docs/formats/owner-packet.md. The parser
# correctly yields zero summaries for these rather than garbage data.
KNOWN_UNSUPPORTED_LAYOUT = {
    "Jan 01, 2021 to Dec 31, 2021.pdf",
    "Jan 01, 2022 to Jan 31, 2022.pdf",
}


@requires_archive
def test_full_archive_parses_without_crashing():
    """dev-plan.md sec 8 step 3: test against every real sample, not just the
    hand-picked ones above. Confirms the parser survives every layout drift
    actually present across the archive (never crashes, never silently
    produces wrong numbers - either extracts correctly or yields nothing) and
    that the cross-check arithmetic holds everywhere a summary IS found."""
    import tempfile
    import zipfile

    failures = []
    checked = 0
    zero_summary_files = []

    for path in all_archive_files():
        if path.suffix not in (".zip", ".pdf"):
            continue
        try:
            if path.suffix == ".zip":
                with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(path) as zf:
                    if "Owner Packet.pdf" not in zf.namelist():
                        continue
                    zf.extract("Owner Packet.pdf", tmp)
                    summaries = parse_owner_packet(f"{tmp}/Owner Packet.pdf")
            else:
                summaries = parse_owner_packet(path)

            checked += 1
            if not summaries:
                zero_summary_files.append(path.name)
                continue

            for summary in summaries:
                f = summary.fields
                if "net_owner_funds" not in f or "ending_cash_balance" not in f:
                    failures.append(f"{path.name} {summary.property_nickname}: missing core fields")
                    continue
                expected = f["ending_cash_balance"] + f.get("unpaid_bills", 0) + f.get("property_reserve", 0)
                if abs(expected - f["net_owner_funds"]) > 0.01:
                    failures.append(
                        f"{path.name} {summary.property_nickname}: arithmetic mismatch "
                        f"(expected {expected}, got {f['net_owner_funds']})"
                    )
        except Exception as exc:  # noqa: BLE001 - we want to collect every failure, not stop at the first
            failures.append(f"{path.name}: {type(exc).__name__}: {exc}")

    assert checked > 40, f"expected to check most of the ~54-file archive, only checked {checked}"
    assert not failures, "parser failures across the real archive:\n" + "\n".join(failures)
    unexpected_zero = set(zero_summary_files) - KNOWN_UNSUPPORTED_LAYOUT
    assert not unexpected_zero, f"unexpectedly found no summaries in: {unexpected_zero}"
