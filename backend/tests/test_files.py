def export_file(client, headers, title="My plan", fmt="pdf", notes="# Plan\n- first idea"):
    return client.post(
        "/api/notes/export",
        json={"title": title, "notes": notes, "format": fmt},
        headers=headers,
    )


def first_conversation(client, headers):
    res = client.post("/api/chat", json={"message": "Make notes about nouns"}, headers=headers)
    return res.get_json()["conversation_id"]


def command(client, headers, cid, **extra):
    body = {
        "conversation_id": cid,
        "command": "Turn it into a Word document",
        "notes": "# Nouns\n- A noun names a person, place or thing",
        "title": "Nouns",
        "formats": ["docx"],
        **extra,
    }
    return client.post("/api/notes/command", json=body, headers=headers)


# ---------- My files ----------

def test_files_require_login(client):
    assert client.get("/api/files").status_code == 401


def test_exported_files_are_kept_and_can_be_downloaded_again(client, auth):
    export_file(client, auth, "My plan", "pdf")

    files = client.get("/api/files", headers=auth).get_json()
    assert len(files) == 1
    assert files[0]["filename"] == "My-plan.pdf"
    assert files[0]["format"] == "pdf"
    assert files[0]["size"] > 0

    res = client.get(f"/api/files/{files[0]['id']}/download", headers=auth)
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert res.data.startswith(b"%PDF")


def test_delete_a_file(client, auth):
    export_file(client, auth)
    fid = client.get("/api/files", headers=auth).get_json()[0]["id"]

    assert client.delete(f"/api/files/{fid}", headers=auth).status_code == 200
    assert client.get("/api/files", headers=auth).get_json() == []
    assert client.get(f"/api/files/{fid}/download", headers=auth).status_code == 404


def test_users_cannot_see_each_others_files(client, make_user):
    alice = make_user("alice", "alice@example.com")
    bob = make_user("bob", "bob@example.com")
    export_file(client, alice)
    fid = client.get("/api/files", headers=alice).get_json()[0]["id"]

    assert client.get("/api/files", headers=bob).get_json() == []
    assert client.get(f"/api/files/{fid}/download", headers=bob).status_code == 404
    assert client.delete(f"/api/files/{fid}", headers=bob).status_code == 404


def test_only_the_newest_50_files_are_kept(client, auth):
    for i in range(51):
        export_file(client, auth, title=f"Note {i}")

    titles = [f["title"] for f in client.get("/api/files", headers=auth).get_json()]
    assert len(titles) == 50
    assert "Note 0" not in titles
    assert "Note 50" in titles


# ---------- "Turn it into a PDF / Word document" typed in the chat ----------

def test_command_creates_files_and_saves_the_exchange(client, auth):
    cid = first_conversation(client, auth)
    res = command(client, auth, cid, formats=["pdf", "docx"])

    assert res.status_code == 200
    data = res.get_json()
    assert [f["filename"] for f in data["files"]] == ["Nouns.pdf", "Nouns.docx"]
    assert data["message"].startswith("Done!")

    # the request and CYNA's note are saved in the chat history
    convo = client.get(f"/api/conversations/{cid}", headers=auth).get_json()
    assert [m["role"] for m in convo["messages"]] == ["user", "assistant", "user", "system"]
    assert convo["messages"][2]["content"] == "Turn it into a Word document"
    assert convo["messages"][3]["content"].startswith("Done!")

    # and the files can be downloaded again
    for f in data["files"]:
        assert client.get(f"/api/files/{f['id']}/download", headers=auth).status_code == 200
    assert len(client.get("/api/files", headers=auth).get_json()) == 2


def test_command_needs_a_format(client, auth):
    cid = first_conversation(client, auth)
    assert command(client, auth, cid, formats=[]).status_code == 400
    assert command(client, auth, cid, formats=["exe"]).status_code == 400


def test_command_needs_notes(client, auth):
    cid = first_conversation(client, auth)
    assert command(client, auth, cid, notes="  ").status_code == 400


def test_command_for_unknown_conversation_returns_404(client, auth):
    assert command(client, auth, 9999).status_code == 404


def test_command_cannot_use_another_users_conversation(client, make_user):
    alice = make_user("alice", "alice@example.com")
    bob = make_user("bob", "bob@example.com")
    cid = first_conversation(client, alice)

    assert command(client, bob, cid).status_code == 404