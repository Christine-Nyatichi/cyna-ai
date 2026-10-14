import json

import routes.chat as chat_routes
from services.ai_service import AIServiceError


def stream(client, headers, message="Hello", **extra):
    return client.post("/api/chat/stream", json={"message": message, **extra}, headers=headers)


def events(response):
    items = []
    for line in response.get_data(as_text=True).split("\n"):
        if line.startswith("data: "):
            items.append(json.loads(line[6:]))
    return items


def test_stream_requires_login(client):
    assert client.post("/api/chat/stream", json={"message": "hi"}).status_code == 401


def test_stream_sends_tokens_then_done_and_saves(client, auth):
    res = stream(client, auth, "Hello CYNA")
    assert res.status_code == 200
    assert res.mimetype == "text/event-stream"

    items = events(res)
    tokens = [e["text"] for e in items if e["type"] == "token"]
    assert "".join(tokens) == "FAKE REPLY"
    assert items[-1]["type"] == "done"

    cid = items[-1]["conversation_id"]
    convo = client.get(f"/api/conversations/{cid}", headers=auth).get_json()
    assert [m["role"] for m in convo["messages"]] == ["user", "assistant"]
    assert convo["messages"][1]["content"] == "FAKE REPLY"


def test_stream_rejects_empty_message(client, auth):
    assert stream(client, auth, "   ").status_code == 400


def test_stream_error_is_reported_and_nothing_is_saved(client, auth, monkeypatch):
    def broken(*args, **kwargs):
        raise AIServiceError("AI is down")
        yield  # makes this a generator

    monkeypatch.setattr(chat_routes, "generate_reply_stream", broken)

    items = events(stream(client, auth, "Hello"))
    assert items[-1]["type"] == "error"
    assert client.get("/api/conversations", headers=auth).get_json() == []


def test_stream_remember_saves_a_memory(client, auth, fake_ai):
    stream(client, auth, "remember that I like Python").get_data()
    assert fake_ai["memories"] == ["I like Python"]
    memories = client.get("/api/memories", headers=auth).get_json()
    assert [m["content"] for m in memories] == ["I like Python"]


def test_stream_continues_an_existing_conversation(client, auth, fake_ai):
    first = events(stream(client, auth, "First"))
    cid = first[-1]["conversation_id"]

    stream(client, auth, "Second", conversation_id=cid).get_data()
    # history sent to the AI: user, assistant, user
    assert len(fake_ai["messages"]) == 3


def test_stream_cannot_use_another_users_conversation(client, make_user):
    alice = make_user("alice", "alice@example.com")
    bob = make_user("bob", "bob@example.com")

    cid = events(stream(client, alice, "Alice's chat"))[-1]["conversation_id"]
    assert stream(client, bob, "Hi", conversation_id=cid).status_code == 404