from flask import Blueprint, jsonify, request

from app.cache import invalidate_all
from app.db import SessionLocal
from app.ingestion import process_upload
from app.models import Document

upload_bp = Blueprint("upload", __name__)


@upload_bp.post("/upload")
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify(error="no files provided"), 400

    uploaded_files = [(f.filename, f.read()) for f in files]

    session = SessionLocal()
    try:
        batch = process_upload(uploaded_files, session)
        needs_review = (
            session.query(Document)
            .filter_by(source_batch_id=batch.id, status="needs_review")
            .count()
        )
        result = dict(
            batch_id=batch.id,
            source=batch.source,
            file_count=batch.file_count,
            needs_review=needs_review,
            notes=batch.notes,
        )
    finally:
        session.close()
    invalidate_all()
    return jsonify(**result)
