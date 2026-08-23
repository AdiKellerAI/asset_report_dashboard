"""Where original uploaded documents get archived (dev-plan.md sec 6 step 6:
"the original document is archived (linked, not deleted) for the audit trail").

Local disk (instance/documents) works for the dev server, but Vercel's
serverless functions have a read-only filesystem except /tmp, which is wiped
between invocations and not shared across instances - so on Vercel this
writes to Vercel Blob instead, selected by the presence of
BLOB_READ_WRITE_TOKEN (the env var Vercel injects once a Blob store is
connected to the project).
"""

import os
from pathlib import Path

DOCUMENTS_DIR = Path(os.environ.get("DOCUMENTS_DIR", "instance/documents"))


def _use_blob_storage() -> bool:
    return bool(os.environ.get("BLOB_READ_WRITE_TOKEN"))


def save_document_file(content_hash: str, extension: str, data: bytes) -> str:
    """Content-addressable storage: filename is the hash itself, so re-saving
    identical bytes is a no-op and naturally can't collide with a different
    file's name. Returns a local path (local disk) or the blob's URL (Vercel
    Blob) - either way, a stable string suitable for `document.storage_path`.
    """
    pathname = f"documents/{content_hash}{extension}"

    if _use_blob_storage():
        import vercel_blob

        existing = vercel_blob.list({"prefix": pathname, "limit": "1"})
        for blob in existing.get("blobs", []):
            if blob["pathname"] == pathname:
                return blob["url"]
        resp = vercel_blob.put(pathname, data)
        return resp["url"]

    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = DOCUMENTS_DIR / f"{content_hash}{extension}"
    if not path.exists():
        path.write_bytes(data)
    return str(path)
