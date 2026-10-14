import json

from flask import Blueprint, request, jsonify, Response, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import Conversation, Message, Memory, Document, DocumentChunk, utcnow
from services.ai_service import generate_reply, generate_reply_stream, AIServiceError
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


def prepare_chat(user_id, data):
    """Checks a chat request and gathers everything the AI needs. Nothing is saved here.

    The result holds only plain values (no database objects), so it is safe to use
    later, while an answer is still streaming.

    Returns (context, None) on success or (None, error_response) on failure.
    """
    text = (data.get("message") or "").strip()
    conversation_id = data.get("conversation_id")
    document_id = data.get("document_id")
    mode = data.get("mode", "general")

    if not text:
        return None, (jsonify({"error": "message is required"}), 400)
    if mode not in VALID_MODES:
        return None, (jsonify({"error": "invalid mode"}), 400)

    doc = None
    if document_id:
        doc = Document.query.filter_by(id=document_id, user_id=user_id).first()
        if not doc:
            return None, (jsonify({"error": "document not found"}), 404)

    conversation = None
    history = []
    if conversation_id:
        conversation = Conversation.query.filter_by(id=conversation_id, user_id=user_id).first()
        if not conversation:
            return None, (jsonify({"error": "conversation not found"}), 404)
        history = [
            {"role": m.role, "content": m.content}
            for m in Message.query.filter_by(conversation_id=conversation.id).order_by(Message.id).all()
        ]
    history.append({"role": "user", "content": text})

    memories = [
        m.content for m in Memory.query.filter_by(user_id=user_id).order_by(Memory.id).all()
    ]

    # "remember ..." messages add a memory, saved once the answer is complete
    to_remember = extract_memory(text)
    if to_remember and len(to_remember) <= MAX_MEMORY_LENGTH and len(memories) < MAX_MEMORIES:
        memories.append(to_remember)
    else:
        to_remember = None

    document_context = None
    if doc:
        chunks = [
            c.content
            for c in DocumentChunk.query.filter_by(document_id=doc.id)
            .order_by(DocumentChunk.chunk_index)
            .all()
        ]
        document_context = {"name": doc.filename, "excerpts": select_context(chunks, text)}

    return {
        "text": text,
        "mode": conversation.mode if conversation else mode,
        "conversation_id": conversation.id if conversation else None,
        "history": history,
        "memories": memories,
        "to_remember": to_remember,
        "document": document_context,
    }, None


def save_exchange(user_id, ctx, reply_text):
    """Saves the user message, the AI reply and any new memory in one go."""
    conversation = None
    if ctx["conversation_id"]:
        conversation = db.session.get(Conversation, ctx["conversation_id"])

    if conversation is None:
        conversation = Conversation(user_id=user_id, title=ctx["text"][:50], mode=ctx["mode"])
        db.session.add(conversation)
        db.session.flush()

    db.session.add(Message(conversation_id=conversation.id, role="user", content=ctx["text"]))
    if ctx["to_remember"]:
        db.session.add(Memory(user_id=user_id, content=ctx["to_remember"]))

    reply = Message(conversation_id=conversation.id, role="assistant", content=reply_text)
    db.session.add(reply)
    conversation.updated_at = utcnow()
    db.session.commit()
    return conversation.id, reply.id


def sse(payload):
    return "data: " + json.dumps(payload) + "\n\n"


@chat_bp.route("/chat", methods=["POST"])
@jwt_required()
def chat():
    user_id = current_user_id()
    ctx, error = prepare_chat(user_id, request.get_json() or {})
    if error:
        return error

    try:
        reply_text = generate_reply(ctx["history"], ctx["mode"], ctx["memories"], ctx["document"])
    except AIServiceError as e:
        return jsonify({"error": str(e)}), 503

    conversation_id, reply_id = save_exchange(user_id, ctx, reply_text)
    reply = db.session.get(Message, reply_id)
    return jsonify({"conversation_id": conversation_id, "reply": serialize_message(reply)})


@chat_bp.route("/chat/stream", methods=["POST"])
@jwt_required()
def chat_stream():
    user_id = current_user_id()
    ctx, error = prepare_chat(user_id, request.get_json() or {})
    if error:
        return error

    def generate():
        pieces = []
        try:
            for piece in generate_reply_stream(
                ctx["history"], ctx["mode"], ctx["memories"], ctx["document"]
            ):
                pieces.append(piece)
                yield sse({"type": "token", "text": piece})
        except AIServiceError as e:
            yield sse({"type": "error", "error": str(e)})
            return

        reply_text = "".join(pieces).strip()
        if not reply_text:
            yield sse({"type": "error", "error": "The AI returned an empty reply"})
            return

        conversation_id, reply_id = save_exchange(user_id, ctx, reply_text)
        yield sse({"type": "done", "conversation_id": conversation_id, "message_id": reply_id})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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