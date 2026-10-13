from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import Conversation, Message, Memory, Document, DocumentChunk
from services.ai_service import generate_reply, AIServiceError
from services.document_service import select_context

chat_bp = Blueprint("chat", __name__, url_prefix="/api")

VALID_MODES = {"general", "study", "coding", "research", "writing", "data"}
MAX_MEMORIES = 50
MAX_MEMORY_LENGTH = 300


def current_user_id():
    return int(get_jwt_identity())


def serialize_message(m):
    return {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}


def serialize_conversation(c):
    return {
        "id": c.id,
        "title": c.title,
        "mode": c.mode,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def extract_memory(text):
    """If the message starts with 'remember ...', return what to remember."""
    lower = text.lower()
    for prefix in ("remember that ", "remember: ", "remember "):
        if lower.startswith(prefix):
            return text[len(prefix):].strip()
    return None


@chat_bp.route("/chat", methods=["POST"])
@jwt_required()
def chat():
    data = request.get_json() or {}
    text = (data.get("message") or "").strip()
    conversation_id = data.get("conversation_id")
    document_id = data.get("document_id")
    mode = data.get("mode", "general")

    if not text:
        return jsonify({"error": "message is required"}), 400
    if mode not in VALID_MODES:
        return jsonify({"error": "invalid mode"}), 400

    user_id = current_user_id()

    # Optional: chat about an uploaded document
    doc = None
    if document_id:
        doc = Document.query.filter_by(id=document_id, user_id=user_id).first()
        if not doc:
            return jsonify({"error": "document not found"}), 404

    if conversation_id:
        conversation = Conversation.query.filter_by(id=conversation_id, user_id=user_id).first()
        if not conversation:
            return jsonify({"error": "conversation not found"}), 404
    else:
        conversation = Conversation(user_id=user_id, title=text[:50], mode=mode)
        db.session.add(conversation)
        db.session.flush()

    db.session.add(Message(conversation_id=conversation.id, role="user", content=text))

    # Save to memory if the user said "remember ..."
    to_remember = extract_memory(text)
    if (
        to_remember
        and len(to_remember) <= MAX_MEMORY_LENGTH
        and Memory.query.filter_by(user_id=user_id).count() < MAX_MEMORIES
    ):
        db.session.add(Memory(user_id=user_id, content=to_remember))
    db.session.flush()

    history = [
        {"role": m.role, "content": m.content}
        for m in Message.query.filter_by(conversation_id=conversation.id).order_by(Message.id).all()
    ]
    memories = [
        m.content for m in Memory.query.filter_by(user_id=user_id).order_by(Memory.id).all()
    ]

    document_context = None
    if doc:
        chunks = [
            c.content
            for c in DocumentChunk.query.filter_by(document_id=doc.id)
            .order_by(DocumentChunk.chunk_index)
            .all()
        ]
        document_context = {"name": doc.filename, "excerpts": select_context(chunks, text)}

    try:
        reply_text = generate_reply(history, conversation.mode, memories, document_context)
    except AIServiceError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 503

    reply = Message(conversation_id=conversation.id, role="assistant", content=reply_text)
    db.session.add(reply)
    db.session.commit()

    return jsonify({"conversation_id": conversation.id, "reply": serialize_message(reply)})


@chat_bp.route("/conversations", methods=["GET"])
@jwt_required()
def list_conversations():
    search = (request.args.get("search") or "").strip()
    query = Conversation.query.filter_by(user_id=current_user_id())
    if search:
        query = query.filter(Conversation.title.ilike(f"%{search}%"))
    conversations = query.order_by(Conversation.updated_at.desc()).all()
    return jsonify([serialize_conversation(c) for c in conversations])


@chat_bp.route("/conversations/<int:conversation_id>", methods=["GET"])
@jwt_required()
def get_conversation(conversation_id):
    c = Conversation.query.filter_by(id=conversation_id, user_id=current_user_id()).first()
    if not c:
        return jsonify({"error": "conversation not found"}), 404
    data = serialize_conversation(c)
    data["messages"] = [serialize_message(m) for m in c.messages]
    return jsonify(data)


@chat_bp.route("/conversations/<int:conversation_id>", methods=["PATCH"])
@jwt_required()
def rename_conversation(conversation_id):
    c = Conversation.query.filter_by(id=conversation_id, user_id=current_user_id()).first()
    if not c:
        return jsonify({"error": "conversation not found"}), 404
    title = ((request.get_json() or {}).get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    c.title = title[:200]
    db.session.commit()
    return jsonify(serialize_conversation(c))


@chat_bp.route("/conversations/<int:conversation_id>", methods=["DELETE"])
@jwt_required()
def delete_conversation(conversation_id):
    c = Conversation.query.filter_by(id=conversation_id, user_id=current_user_id()).first()
    if not c:
        return jsonify({"error": "conversation not found"}), 404
    db.session.delete(c)
    db.session.commit()
    return jsonify({"message": "conversation deleted"})