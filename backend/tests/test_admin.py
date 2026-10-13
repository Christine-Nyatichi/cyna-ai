from app import app as flask_app
from extensions import db
from models import User


def make_admin(email):
    with flask_app.app_context():
        user = User.query.filter_by(email=email).first()
        user.role = "admin"
        db.session.commit()


def test_admin_stats_require_login(client):
    assert client.get("/api/admin/stats").status_code == 401


def test_regular_user_is_forbidden(client, auth):
    assert client.get("/api/admin/stats", headers=auth).status_code == 403


def test_cannot_make_yourself_admin_when_registering(client):
    client.post(
        "/api/auth/register",
        json={"username": "sneaky", "email": "sneaky@example.com", "password": "password123", "role": "admin"},
    )
    login = client.post("/api/auth/login", json={"email": "sneaky@example.com", "password": "password123"})
    headers = {"Authorization": "Bearer " + login.get_json()["token"]}
    assert client.get("/api/admin/stats", headers=headers).status_code == 403


def test_admin_can_see_stats(client, auth):
    make_admin("christine@example.com")
    client.post("/api/chat", json={"message": "hi"}, headers=auth)
    client.post("/api/tasks", json={"title": "A task"}, headers=auth)

    res = client.get("/api/admin/stats", headers=auth)
    assert res.status_code == 200
    data = res.get_json()

    assert data["totals"]["users"] == 1
    assert data["totals"]["conversations"] == 1
    assert data["totals"]["messages"] == 2
    assert data["totals"]["tasks"] == 1
    assert data["last_24h"]["ai_replies"] == 1
    assert data["last_24h"]["requests"] >= 2
    assert len(data["requests_per_day"]) == 7
    assert data["recent_users"][0]["username"] == "christine"


def test_errors_are_counted(client, auth):
    make_admin("christine@example.com")
    client.get("/api/conversations/9999", headers=auth)  # 404

    data = client.get("/api/admin/stats", headers=auth).get_json()
    assert data["last_24h"]["errors"] >= 1
    assert any(e["status_code"] == 404 for e in data["recent_errors"])


def test_stats_do_not_leak_messages_or_password_hashes(client, auth):
    make_admin("christine@example.com")
    client.post("/api/chat", json={"message": "my very private words"}, headers=auth)

    text = client.get("/api/admin/stats", headers=auth).get_data(as_text=True)
    assert "my very private words" not in text
    assert "password_hash" not in text