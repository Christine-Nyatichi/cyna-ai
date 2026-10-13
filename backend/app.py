import os
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, jsonify, Response
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from sqlalchemy import text

from extensions import db
import models  # noqa: F401  (registers the tables)
from routes.auth import auth_bp
from routes.chat import chat_bp
from routes.memory import memory_bp
from routes.tasks import tasks_bp
from routes.documents import documents_bp

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=8)
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # hard upload limit

db.init_app(app)
JWTManager(app)
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(memory_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(documents_bp)

with app.app_context():
    db.create_all()


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "file is too large (max 5 MB)"}), 413


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