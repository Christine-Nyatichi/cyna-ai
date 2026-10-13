from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import Memory

memory_bp = Blueprint("memory", __name__, url_prefix="/api/memories")

MAX_MEMORIES = 50
MAX_LENGTH = 300


def current_user_id():
    return int(get_jwt_identity())


def serialize(m):
    return {"id": m.id, "content": m.content, "created_at": m.created_at.isoformat()}


@memory_bp.route("", methods=["GET"])
@jwt_required()
def list_memories():
    items = Memory.query.filter_by(user_id=current_user_id()).order_by(Memory.id.desc()).all()
    return jsonify([serialize(m) for m in items])


@memory_bp.route("", methods=["POST"])
@jwt_required()
def add_memory():
    content = ((request.get_json() or {}).get("content") or "").strip()
    user_id = current_user_id()

    if not content:
        return jsonify({"error": "content is required"}), 400
    if len(content) > MAX_LENGTH:
        return jsonify({"error": f"keep it under {MAX_LENGTH} characters"}), 400
    if Memory.query.filter_by(user_id=user_id).count() >= MAX_MEMORIES:
        return jsonify({"error": f"memory is full ({MAX_MEMORIES} items). Delete some first."}), 400

    m = Memory(user_id=user_id, content=content)
    db.session.add(m)
    db.session.commit()
    return jsonify(serialize(m)), 201


@memory_bp.route("/<int:memory_id>", methods=["DELETE"])
@jwt_required()
def delete_memory(memory_id):
    m = Memory.query.filter_by(id=memory_id, user_id=current_user_id()).first()
    if not m:
        return jsonify({"error": "memory not found"}), 404
    db.session.delete(m)
    db.session.commit()
    return jsonify({"message": "deleted"})


@memory_bp.route("", methods=["DELETE"])
@jwt_required()
def clear_memories():
    Memory.query.filter_by(user_id=current_user_id()).delete()
    db.session.commit()
    return jsonify({"message": "all memories deleted"})