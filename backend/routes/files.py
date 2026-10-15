from flask import Blueprint, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import GeneratedFile
from services.notes_service import DOCX_MIMETYPE, safe_filename

files_bp = Blueprint("files", __name__, url_prefix="/api/files")


def current_user_id():
    return int(get_jwt_identity())


def filename_for(title, fmt):
    return f"{safe_filename(title)}.{fmt}"


@files_bp.route("", methods=["GET"])
@jwt_required()
def list_files():
    rows = (
        db.session.query(
            GeneratedFile.id,
            GeneratedFile.title,
            GeneratedFile.format,
            GeneratedFile.size,
            GeneratedFile.created_at,
        )
        .filter(GeneratedFile.user_id == current_user_id())
        .order_by(GeneratedFile.id.desc())
        .all()
    )
    return jsonify(
        [
            {
                "id": r.id,
                "title": r.title,
                "format": r.format,
                "size": r.size,
                "filename": filename_for(r.title, r.format),
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    )


@files_bp.route("/<int:file_id>/download", methods=["GET"])
@jwt_required()
def download_file(file_id):
    record = GeneratedFile.query.filter_by(id=file_id, user_id=current_user_id()).first()
    if not record:
        return jsonify({"error": "file not found"}), 404

    mimetype = "application/pdf" if record.format == "pdf" else DOCX_MIMETYPE
    filename = filename_for(record.title, record.format)
    return Response(
        record.content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@files_bp.route("/<int:file_id>", methods=["DELETE"])
@jwt_required()
def delete_file(file_id):
    record = GeneratedFile.query.filter_by(id=file_id, user_id=current_user_id()).first()
    if not record:
        return jsonify({"error": "file not found"}), 404
    db.session.delete(record)
    db.session.commit()
    return jsonify({"message": "file deleted"})