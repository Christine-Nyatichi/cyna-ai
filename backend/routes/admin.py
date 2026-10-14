import re
from datetime import timedelta
from functools import wraps

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

from extensions import db
from models import User, Conversation, Message, Document, Task, Memory, UsageLog, utcnow

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = db.session.get(User, int(get_jwt_identity()))
        if not user or user.role != "admin":
            return jsonify({"error": "admin access required"}), 403
        return fn(*args, **kwargs)

    return jwt_required()(wrapper)


@admin_bp.route("/stats", methods=["GET"])
@admin_required
def stats():
    now = utcnow()
    day_ago = now - timedelta(days=1)
    week_start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)

    totals = {
        "users": User.query.count(),
        "conversations": Conversation.query.count(),
        "messages": Message.query.count(),
        "documents": Document.query.count(),
        "tasks": Task.query.count(),
        "memories": Memory.query.count(),
        "new_users_7d": User.query.filter(User.created_at >= week_start).count(),
    }

    last_24h = {
        "requests": UsageLog.query.filter(UsageLog.created_at >= day_ago).count(),
        "errors": UsageLog.query.filter(
            UsageLog.created_at >= day_ago, UsageLog.status_code >= 400
        ).count(),
        "active_users": db.session.query(func.count(func.distinct(UsageLog.user_id)))
        .filter(UsageLog.created_at >= day_ago, UsageLog.user_id.isnot(None))
        .scalar()
        or 0,
        "ai_replies": UsageLog.query.filter(
            UsageLog.created_at >= day_ago,
                        UsageLog.endpoint.in_(["POST /api/chat", "POST /api/chat/stream"]),
            UsageLog.status_code == 200,
        ).count(),
    }

    # Requests per day for the last 7 days
    day_expr = func.date(UsageLog.created_at)
    rows = (
        db.session.query(day_expr, func.count(UsageLog.id))
        .filter(UsageLog.created_at >= week_start)
        .group_by(day_expr)
        .all()
    )
    counts = {str(day): count for day, count in rows}
    requests_per_day = []
    for i in range(7):
        day = (week_start + timedelta(days=i)).date().isoformat()
        requests_per_day.append({"date": day, "requests": counts.get(day, 0)})

    # Most used endpoints (ids are collapsed, so /api/tasks/5 and /api/tasks/9 count together)
    endpoint_rows = (
        db.session.query(UsageLog.endpoint, func.count(UsageLog.id))
        .filter(UsageLog.created_at >= week_start)
        .group_by(UsageLog.endpoint)
        .all()
    )
    merged = {}
    for endpoint, count in endpoint_rows:
        key = re.sub(r"/\d+", "/<id>", endpoint or "unknown")
        merged[key] = merged.get(key, 0) + count
    top_endpoints = [
        {"endpoint": key, "count": value}
        for key, value in sorted(merged.items(), key=lambda kv: -kv[1])[:8]
    ]

    recent_errors = [
        {
            "endpoint": e.endpoint,
            "status_code": e.status_code,
            "user_id": e.user_id,
            "created_at": e.created_at.isoformat(),
        }
        for e in UsageLog.query.filter(UsageLog.status_code >= 400)
        .order_by(UsageLog.id.desc())
        .limit(10)
        .all()
    ]

    conversation_counts = dict(
        db.session.query(Conversation.user_id, func.count(Conversation.id))
        .group_by(Conversation.user_id)
        .all()
    )
    recent_users = [
        {
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "created_at": u.created_at.isoformat(),
            "conversations": conversation_counts.get(u.id, 0),
        }
        for u in User.query.order_by(User.id.desc()).limit(10).all()
    ]

    return jsonify(
        {
            "totals": totals,
            "last_24h": last_24h,
            "requests_per_day": requests_per_day,
            "top_endpoints": top_endpoints,
            "recent_errors": recent_errors,
            "recent_users": recent_users,
        }
    )