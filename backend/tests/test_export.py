def chat_once(client, headers, message="Explain APIs"):
    res = client.post("/api/chat", json={"message": message}, headers=headers)
    return res.get_json()["conversation_id"]


def test_export_requires_login(client):
    assert client.get("/api/conversations/1/export").status_code == 401


def test_export_markdown_is_the_default(client, auth):
    cid = chat_once(client, auth, "Explain APIs")
    res = client.get(f"/api/conversations/{cid}/export", headers=auth)

    assert res.status_code == 200
    assert res.mimetype == "text/markdown"
    assert "attachment" in res.headers["Content-Disposition"]
    assert ".md" in res.headers["Content-Disposition"]

    text = res.get_data(as_text=True)
    assert text.startswith("# Explain APIs")
    assert "**You**" in text
    assert "**CYNA**" in text
    assert "FAKE REPLY" in text


def test_export_plain_text(client, auth):
    cid = chat_once(client, auth, "Explain APIs")
    res = client.get(f"/api/conversations/{cid}/export?format=txt", headers=auth)

    assert res.status_code == 200
    assert res.mimetype == "text/plain"
    assert ".txt" in res.headers["Content-Disposition"]

    text = res.get_data(as_text=True)
    assert "[You," in text
    assert "[CYNA," in text
    assert "FAKE REPLY" in text


def test_export_rejects_unknown_format(client, auth):
    cid = chat_once(client, auth)
    assert client.get(f"/api/conversations/{cid}/export?format=pdf", headers=auth).status_code == 400


def test_export_unknown_conversation_returns_404(client, auth):
    assert client.get("/api/conversations/9999/export", headers=auth).status_code == 404


def test_export_of_another_users_chat_returns_404(client, make_user):
    alice = make_user("alice", "alice@example.com")
    bob = make_user("bob", "bob@example.com")
    cid = chat_once(client, alice, "Alice's private chat")

    assert client.get(f"/api/conversations/{cid}/export", headers=bob).status_code == 404


def test_export_filename_is_made_safe(client, auth):
    cid = chat_once(client, auth, "Hello / world?")
    res = client.get(f"/api/conversations/{cid}/export", headers=auth)
    assert 'filename="Hello-world.md"' in res.headers["Content-Disposition"]