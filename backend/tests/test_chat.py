import routes.chat as chat_routes
from services.ai_service import AIServiceError


def send(client, headers, message="Hello", **extra):
    return client.post("/api/chat", json={"message": message, **extra}, headers=headers)


def test_chat_requires_login(client):
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 401


def test_chat_returns_reply_and_saves_messages(client, auth):
    res = send(client, auth, "Hello CYNA")
    assert res.status_code == 200
    data = res.get_json()
    assert data["reply"]["content"] == "FAKE REPLY"

    convo = client.get(f"/api/conversations/{data['conversation_id']}", headers=auth).get_json()
    assert convo["title"] == "Hello CYNA"
    assert [m["role"] for m in convo["messages"]] == ["user", "assistant"]


def test_chat_continues_existing_conversation(client, auth, fake_ai):
    first = send(client, auth, "First").get_json()
    send(client, auth, "Second", conversation_id=first["conversation_id"])
    # history sent to the AI: user, assistant, user
    assert len(fake_ai["messages"]) == 3


def test_empty_message_is_rejected(client, auth):
    assert send(client, auth, "   ").status_code == 400


def test_invalid_mode_is_rejected(client, auth):
    assert send(client, auth, "hi", mode="hacker").status_code == 400


def test_mode_is_passed_to_the_ai(client, auth, fake_ai):
    send(client, auth, "Explain APIs", mode="study")
    assert fake_ai["mode"] == "study"


def test_unknown_conversation_returns_404(client, auth):
    assert send(client, auth, "hi", conversation_id=9999).status_code == 404


def test_remember_saves_a_memory_and_uses_it(client, auth, fake_ai):
    send(client, auth, "remember that I like Python")
    assert fake_ai["memories"] == ["I like Python"]
    memories = client.get("/api/memories", headers=auth).get_json()
    assert [m["content"] for m in memories] == ["I like Python"]


def test_saved_memories_are_sent_to_the_ai(client, auth, fake_ai):
    client.post("/api/memories", json={"content": "My favourite language is Python"}, headers=auth)
    send(client, auth, "What is my favourite language?")
    assert fake_ai["memories"] == ["My favourite language is Python"]


def test_ai_failure_returns_503_and_saves_nothing(client, auth, monkeypatch):
    def broken(*args, **kwargs):
        raise AIServiceError("AI is down")

    monkeypatch.setattr(chat_routes, "generate_reply", broken)
    res = send(client, auth, "Hello")
    assert res.status_code == 503
    assert client.get("/api/conversations", headers=auth).get_json() == []


def test_list_and_search_conversations(client, auth):
    send(client, auth, "Python question")
    send(client, auth, "Cooking question")
    assert len(client.get("/api/conversations", headers=auth).get_json()) == 2

    found = client.get("/api/conversations?search=python", headers=auth).get_json()
    assert len(found) == 1
    assert found[0]["title"] == "Python question"


def test_rename_conversation(client, auth):
    cid = send(client, auth, "Old title").get_json()["conversation_id"]
    res = client.patch(f"/api/conversations/{cid}", json={"title": "New title"}, headers=auth)
    assert res.status_code == 200
    assert res.get_json()["title"] == "New title"


def test_rename_requires_a_title(client, auth):
    cid = send(client, auth, "Hello").get_json()["conversation_id"]
    res = client.patch(f"/api/conversations/{cid}", json={"title": " "}, headers=auth)
    assert res.status_code == 400


def test_delete_conversation(client, auth):
    cid = send(client, auth, "Delete me").get_json()["conversation_id"]
    assert client.delete(f"/api/conversations/{cid}", headers=auth).status_code == 200
    assert client.get(f"/api/conversations/{cid}", headers=auth).status_code == 404


def test_users_cannot_see_each_others_chats(client, make_user):
    alice = make_user("alice", "alice@example.com")
    bob = make_user("bob", "bob@example.com")

    cid = send(client, alice, "Alice's secret").get_json()["conversation_id"]

    assert client.get(f"/api/conversations/{cid}", headers=bob).status_code == 404
    assert client.patch(f"/api/conversations/{cid}", json={"title": "hacked"}, headers=bob).status_code == 404
    assert client.delete(f"/api/conversations/{cid}", headers=bob).status_code == 404
    assert client.get("/api/conversations", headers=bob).get_json() == []