from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import Conversation, GeneratedFile, Message, utcnow
from services.ai_service import generate_reply, AIServiceError
from services.notes_service import (
    DOCX_MIMETYPE,
    build_docx,
    build_pdf,
    parse_notes,
    safe_filename,
)

notes_bp = Blueprint("notes", __name__, url_prefix="/api/notes")

MAX_NOTES_CHARS = 20000
MAX_TOPIC_CHARS = 300
MAX_FILES_PER_USER = 50


def current_user_id():
    return int(get_jwt_identity())


def write_notes(topic):
    """Asks the AI to write study notes about a topic."""
    return generate_reply(
        [{"role": "user", "content": f"Write study notes about: {topic}"}],
        mode="notes_writer",
    ).strip()


def make_file(title, blocks, fmt):
    if fmt == "pdf":
        return build_pdf(title, blocks), "application/pdf"
    return build_docx(title, blocks), DOCX_MIMETYPE


def store_file(user_id, title, fmt, body):
    """Keeps a copy of the file so it can be downloaded again. Only the newest files are kept."""
    count = GeneratedFile.query.filter_by(user_id=user_id).count()
    while count >= MAX_FILES_PER_USER:
        oldest = GeneratedFile.query.filter_by(user_id=user_id).order_by(GeneratedFile.id).first()
        db.session.delete(oldest)
        count -= 1

    record = GeneratedFile(
        user_id=user_id,
        title=title[:120],
        format=fmt,
        size=len(body),
        content=body,
    )
    db.session.add(record)
    db.session.commit()
    return record


@notes_bp.route("/generate", methods=["POST"])
@jwt_required()
def generate_notes():
    topic = ((request.get_json() or {}).get("topic") or "").strip()

    if not topic:
        return jsonify({"error": "tell CYNA what to write notes about"}), 400
    if len(topic) > MAX_TOPIC_CHARS:
        return jsonify({"error": f"keep the topic under {MAX_TOPIC_CHARS} characters"}), 400

    try:
        notes = write_notes(topic)
    except AIServiceError as e:
        return jsonify({"error": str(e)}), 503

    return jsonify({"notes": notes, "title": topic[:60]})


@notes_bp.route("/export", methods=["POST"])
@jwt_required()
def export_notes():
    data = request.get_json() or {}
    title = (data.get("title") or "").strip()[:120]
    notes = (data.get("notes") or "").strip()
    topic = (data.get("topic") or "").strip()
    fmt = data.get("format", "pdf")
    organize = bool(data.get("organize"))

    if not notes and not topic:
        return jsonify({"error": "write some notes or tell CYNA what to write notes about"}), 400
    if len(notes) > MAX_NOTES_CHARS:
        return jsonify({"error": f"notes are too long (max {MAX_NOTES_CHARS} characters)"}), 400
    if len(topic) > MAX_TOPIC_CHARS:
        return jsonify({"error": f"keep the topic under {MAX_TOPIC_CHARS} characters"}), 400
    if fmt not in ("pdf", "docx"):
        return jsonify({"error": "format must be pdf or docx"}), 400

    try:
        if not notes:
            # No notes given: CYNA writes them from the topic
            notes = write_notes(topic)
            title = title or topic[:60]
        elif organize:
            notes = generate_reply([{"role": "user", "content": notes}], mode="notes").strip()
    except AIServiceError as e:
        return jsonify({"error": str(e)}), 503

    title = title or "My notes"
    body, mimetype = make_file(title, parse_notes(notes), fmt)
    store_file(current_user_id(), title, fmt, body)

    filename = f"{safe_filename(title)}.{fmt}"
    return Response(
        body,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@notes_bp.route("/command", methods=["POST"])
@jwt_required()
def file_command():
    """Handles "turn it into a PDF / Word document" typed in the chat.

    Creates the file(s) from CYNA's last answer and saves the exchange in the conversation.
    """
    user_id = current_user_id()
    data = request.get_json() or {}

    command = (data.get("command") or "").strip()[:500]
    notes = (data.get("notes") or "").strip()
    title = (data.get("title") or "").strip()[:120] or "CYNA notes"
    requested = data.get("formats") or []
    formats = [f for f in ("pdf", "docx") if f in requested]

    if not command or not notes or not formats:
        return jsonify({"error": "command, notes and at least one format are required"}), 400
    if len(notes) > MAX_NOTES_CHARS:
        return jsonify({"error": f"notes are too long (max {MAX_NOTES_CHARS} characters)"}), 400

    conversation = Conversation.query.filter_by(
        id=data.get("conversation_id"), user_id=user_id
    ).first()
    if not conversation:
        return jsonify({"error": "conversation not found"}), 404
    conversation_id = conversation.id

    blocks = parse_notes(notes)
    files = []
    for fmt in formats:
        body, _ = make_file(title, blocks, fmt)
        record = store_file(user_id, title, fmt, body)
        files.append(
            {"id": record.id, "filename": f"{safe_filename(title)}.{fmt}", "format": fmt}
        )

    names = " and ".join(f["filename"] for f in files)
    message = (
        f"Done! I made {names} from my last answer. "
        "You can download it again anytime from My files."
    )

    conversation = db.session.get(Conversation, conversation_id)
    db.session.add(Message(conversation_id=conversation_id, role="user", content=command))
    db.session.add(Message(conversation_id=conversation_id, role="system", content=message))
    conversation.updated_at = utcnow()
    db.session.commit()

    return jsonify({"files": files, "message": message})