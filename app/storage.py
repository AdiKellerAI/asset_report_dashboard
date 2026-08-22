"""Where original uploaded documents get archived (dev-plan.md sec 6 step 6:
"the original document is archived (linked, not deleted) for the audit trail").
"""

import os
from pathlib import Path

DOCUMENTS_DIR = Path(os.environ.get("DOCUMENTS_DIR", "instance/documents"))


def save_document_file(content_hash: str, extension: str, data: bytes) -> str:
    """Content-addressable storage: filename is the hash itself, so re-saving
    identical bytes is a no-op and naturally can't collide with a different
    file's name."""
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = DOCUMENTS_DIR / f"{content_hash}{extension}"
    if not path.exists():
        path.write_bytes(data)
    return str(path)
