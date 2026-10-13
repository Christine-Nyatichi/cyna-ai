from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import Task

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")

MAX_TITLE = 200


def current_user_id():
    return int(get_jwt_identity())


def serialize(t):
    return {
        "id": t.id,
        "title": t.title,
        "is_completed": t.is_completed,
        "created_at": t.created_at.isoformat(),
    }


@tasks_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    tasks = (
        Task.query.filter_by(user_id=current_user_id())
        .order_by(Task.is_completed, Task.id.desc())
        .all()
    )
    return jsonify([serialize(t) for t in tasks])


@tasks_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    title = ((request.get_json() or {}).get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    if len(title) > MAX_TITLE:
        return jsonify({"error": f"keep the title under {MAX_TITLE} characters"}), 400

    task = Task(user_id=current_user_id(), title=title)
    db.session.add(task)
    db.session.commit()
    return jsonify(serialize(task)), 201


@tasks_bp.route("/<int:task_id>", methods=["PATCH"])
@jwt_required()
def update_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user_id()).first()
    if not task:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json() or {}

    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            return jsonify({"error": "title cannot be empty"}), 400
        if len(title) > MAX_TITLE:
            return jsonify({"error": f"keep the title under {MAX_TITLE} characters"}), 400
        task.title = title

    if "is_completed" in data:
        task.is_completed = bool(data["is_completed"])

    db.session.commit()
    return jsonify(serialize(task))


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user_id()).first()
    if not task:
        return jsonify({"error": "task not found"}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "task deleted"})