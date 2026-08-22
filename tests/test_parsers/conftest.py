import zipfile
from pathlib import Path

import pytest

ARCHIVE_DIR = Path("/Users/adikeller/Documents/assets/overland_reports")

# Sample files spanning distinct eras identified in the format notes (docs/formats/
# owner-packet.md): 2022 pre-Income-Statement / 2023 first Owner Disbursements +
# Please Remit Balance Due / 2024 multi-work-order / 2025 first no-monthly-payout
# month / 2026 new letterhead + large accumulated balance.
SAMPLE_FILES = [
    "Apr 01, 2022 to Apr 30, 2022.zip",
    "Aug 01, 2023 to Aug 31, 2023.zip",
    "Mar 01, 2024 to Mar 31, 2024.zip",
    "Jan 01, 2025 to Jan 31, 2025.zip",
    "May 01, 2026 to May 31, 2026.zip",
]

requires_archive = pytest.mark.skipif(
    not ARCHIVE_DIR.is_dir(), reason="overland_reports archive not present on this machine"
)


def owner_packet_path(filename, tmp_path):
    """Return a filesystem path to that month's Owner Packet.pdf, extracting from
    the zip into tmp_path first if needed."""
    src = ARCHIVE_DIR / filename
    if src.suffix == ".pdf":
        return src
    with zipfile.ZipFile(src) as zf:
        zf.extract("Owner Packet.pdf", tmp_path)
    return tmp_path / "Owner Packet.pdf"


def all_archive_files():
    if not ARCHIVE_DIR.is_dir():
        return []
    return sorted(ARCHIVE_DIR.iterdir())
