import os

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import Document, DocumentChunk
from services.document_service import extract_text, chunk_text

documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")

ALLOWED_TYPES = {"pdf", "docx", "txt"}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_CHARS = 300000


def current_user_id():
    return int(get_jwt_identity())


def serialize(d):
    return {
        "id": d.id,
        "filename": d.filename,
        "file_type": d.file_type,
        "file_size": d.file_size,
        "uploaded_at": d.uploaded_at.isoformat(),
    }


@documents_bp.route("", methods=["POST"])
@jwt_required()
def upload_document():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "no file uploaded"}), 400

    filename = file.filename[:255]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_TYPES:
        return jsonify({"error": "only PDF, DOCX and TXT files are allowed"}), 400

    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > MAX_SIZE:
        return jsonify({"error": "file is too large (max 5 MB)"}), 413

    try:
        text = extract_text(file.stream, ext)
    except Exception:
        return jsonify({"error": "could not read this file"}), 400

    text = text.strip()
    if not text:
        return jsonify({"error": "no text found in this file (scanned PDFs are not supported yet)"}), 400

    chunks = chunk_text(text[:MAX_CHARS])

    doc = Document(user_id=current_user_id(), filename=filename, file_type=ext, file_size=size)
    db.session.add(doc)
    db.session.flush()
    db.session.add_all(
        [DocumentChunk(document_id=doc.id, chunk_index=i, content=c) for i, c in enumerate(chunks)]
    )
    db.session.commit()
    return jsonify(serialize(doc)), 201


@documents_bp.route("", methods=["GET"])
@jwt_required()
def list_documents():
    docs = Document.query.filter_by(user_id=current_user_id()).order_by(Document.id.desc()).all()
    return jsonify([serialize(d) for d in docs])


@documents_bp.route("/<int:document_id>", methods=["DELETE"])
@jwt_required()
def delete_document(document_id):
    doc = Document.query.filter_by(id=document_id, user_id=current_user_id()).first()
    if not doc:
        return jsonify({"error": "document not found"}), 404
    db.session.delete(doc)
    db.session.commit()
    return jsonify({"message": "document deleted"})