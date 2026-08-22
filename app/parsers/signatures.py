"""Rule-based document type detection (dev-plan.md sec 3, docs/formats/*.md).

Deliberately simple string matching, not model-based - a document that matches
no known signature should fall through to a manual review queue rather than be
guessed at.
"""

OWNER_PACKET = "owner_packet"
WATER_BILL = "water_bill"
SEWER_BILL = "sewer_bill"
UNKNOWN = "unknown"


def detect_document_type(text: str) -> str:
    if "Property Cash Summary" in text:
        return OWNER_PACKET
    if "City of Cleveland Division of Water" in text:
        return WATER_BILL
    if "neorsd.org" in text or "Northeast Ohio Regional Sewer District" in text:
        return SEWER_BILL
    return UNKNOWN
