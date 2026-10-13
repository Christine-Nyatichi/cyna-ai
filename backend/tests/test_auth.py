from app import app as flask_app
from extensions import limiter
from models import User, UsageLog

VALID = {"username": "christine", "email": "christine@example.com", "password": "password123"}


def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_register_success(client):
    res = client.post("/api/auth/register", json=VALID)
    assert res.status_code == 201
    assert res.get_json()["message"] == "account created"


def test_register_duplicate_is_rejected(client):
    client.post("/api/auth/register", json=VALID)
    res = client.post("/api/auth/register", json=VALID)
    assert res.status_code == 409


def test_register_requires_all_fields(client):
    res = client.post("/api/auth/register", json={"email": "a@b.com"})
    assert res.status_code == 400


def test_register_rejects_short_password(client):
    res = client.post("/api/auth/register", json={**VALID, "password": "abc123"})
    assert res.status_code == 400


def test_register_rejects_password_without_numbers(client):
    res = client.post("/api/auth/register", json={**VALID, "password": "abcdefghij"})
    assert res.status_code == 400


def test_register_rejects_invalid_email(client):
    res = client.post("/api/auth/register", json={**VALID, "email": "not-an-email"})
    assert res.status_code == 400


def test_register_rejects_bad_username(client):
    res = client.post("/api/auth/register", json={**VALID, "username": "a b!"})
    assert res.status_code == 400


def test_password_is_stored_hashed(client):
    client.post("/api/auth/register", json=VALID)
    with flask_app.app_context():
        user = User.query.filter_by(email=VALID["email"]).first()
        assert user.password_hash != VALID["password"]
        assert len(user.password_hash) > 20


def test_login_success_returns_token(client):
    client.post("/api/auth/register", json=VALID)
    res = client.post("/api/auth/login", json={"email": VALID["email"], "password": VALID["password"]})
    assert res.status_code == 200
    assert res.get_json()["token"]


def test_login_wrong_password(client):
    client.post("/api/auth/register", json=VALID)
    res = client.post("/api/auth/login", json={"email": VALID["email"], "password": "wrongpass1"})
    assert res.status_code == 401


def test_login_unknown_user(client):
    res = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "password123"})
    assert res.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_token(client, auth):
    res = client.get("/api/auth/me", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["username"] == "christine"


def test_fake_token_is_rejected(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert res.status_code in (401, 422)


def test_login_is_rate_limited(client):
    limiter.enabled = True
    limiter.reset()
    try:
        codes = [
            client.post("/api/auth/login", json={"email": "x@x.com", "password": "wrong"}).status_code
            for _ in range(12)
        ]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert 429 in codes


def test_security_headers_are_set(client):
    res = client.get("/api/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"


def test_requests_are_logged(client, auth):
    client.get("/api/tasks", headers=auth)
    with flask_app.app_context():
        logs = UsageLog.query.filter_by(endpoint="GET /api/tasks").all()
        assert len(logs) == 1
        assert logs[0].status_code == 200
        assert logs[0].user_id is not None