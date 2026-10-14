import os

# Use a throwaway in-memory database and fake keys. This must happen before the app is imported.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-only-for-tests-0123456789"
os.environ["GEMINI_API_KEY"] = "test-key"

import pytest

from app import app as flask_app
from extensions import db, limiter
import routes.chat as chat_routes

# Rate limits are switched on only in the one test that checks them
limiter.enabled = False


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    """Replace the real AI with a fake one that records what it was given."""
    calls = {}

    def record(messages, mode, memories, document):
        calls["messages"] = messages
        calls["mode"] = mode
        calls["memories"] = memories
        calls["document"] = document

    def fake_generate_reply(messages, mode="general", memories=None, document=None):
        record(messages, mode, memories, document)
        return "FAKE REPLY"

    def fake_generate_reply_stream(messages, mode="general", memories=None, document=None):
        record(messages, mode, memories, document)
        yield "FAKE "
        yield "REPLY"

    monkeypatch.setattr(chat_routes, "generate_reply", fake_generate_reply)
    monkeypatch.setattr(chat_routes, "generate_reply_stream", fake_generate_reply_stream)
    return calls


@pytest.fixture()
def client():
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
    with flask_app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def make_user(client):
    """Creates an account, logs in, and returns the auth header."""

    def _make(username="christine", email="christine@example.com", password="password123"):
        client.post(
            "/api/auth/register",
            json={"username": username, "email": email, "password": password},
        )
        res = client.post("/api/auth/login", json={"email": email, "password": password})
        return {"Authorization": "Bearer " + res.get_json()["token"]}

    return _make


@pytest.fixture()
def auth(make_user):
    return make_user()