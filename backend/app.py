import os
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, jsonify, Response, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity
from sqlalchemy import text

load_dotenv()

from extensions import db, limiter
from models import UsageLog
from routes.auth import auth_bp
from routes.chat import chat_bp
from routes.memory import memory_bp
from routes.tasks import tasks_bp
from routes.documents import documents_bp
from routes.admin import admin_bp

if not os.getenv("JWT_SECRET_KEY"):
    raise RuntimeError("JWT_SECRET_KEY is missing in .env")

app = Flask(__name__)

# Only your own frontend may call the API
CORS(app, origins=["http://127.0.0.1:5500", "http://localhost:5500"])

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=8)
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # hard upload limit

db.init_app(app)
limiter.init_app(app)
JWTManager(app)

# Extra limits for the expensive endpoints
limiter.limit("60 per minute")(chat_bp)
limiter.limit("20 per minute")(documents_bp)

app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(memory_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(admin_bp)

with app.app_context():
    db.create_all()


@app.after_request
def secure_and_log(response):
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"

    # Usage log: who called which endpoint and what status came back (no bodies, no passwords)
    path = request.path
    if path.startswith("/api/") and path != "/api/health" and request.method != "OPTIONS":
        try:
            user_id = None
            try:
                verify_jwt_in_request(optional=True)
                identity = get_jwt_identity()
                user_id = int(identity) if identity else None
            except Exception:
                user_id = None

            db.session.add(
                UsageLog(
                    user_id=user_id,
                    endpoint=f"{request.method} {path}"[:200],
                    status_code=response.status_code,
                )
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
    return response


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "file is too large (max 5 MB)"}), 413


@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"error": "too many requests, please slow down and try again shortly"}), 429


@app.route("/api/health", methods=["GET"])
def health():
    try:
        db.session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"
    return jsonify({"status": "ok", "app": "CYNA AI", "database": db_status})


@app.route("/favicon.ico")
def favicon():
    return Response(status=204)


if __name__ == "__main__":
    app.run(debug=True, port=5001)