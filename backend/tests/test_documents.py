import io

from docx import Document as DocxDocument
from pypdf import PdfWriter

from services.document_service import chunk_text, select_context


def upload(client, headers, content, filename):
    return client.post(
        "/api/documents",
        data={"file": (io.BytesIO(content), filename)},
        headers=headers,
        content_type="multipart/form-data",
    )


def send(client, headers, message, **extra):
    return client.post("/api/chat", json={"message": message, **extra}, headers=headers)


# ---------- Upload ----------

def test_documents_require_login(client):
    assert client.get("/api/documents").status_code == 401


def test_upload_txt(client, auth):
    res = upload(client, auth, b"Cats are great. Dogs are loyal.", "notes.txt")
    assert res.status_code == 201
    assert res.get_json()["filename"] == "notes.txt"

    docs = client.get("/api/documents", headers=auth).get_json()
    assert [d["filename"] for d in docs] == ["notes.txt"]


def test_upload_docx(client, auth):
    doc = DocxDocument()
    doc.add_paragraph("Hello from a Word document")
    buffer = io.BytesIO()
    doc.save(buffer)

    res = upload(client, auth, buffer.getvalue(), "report.docx")
    assert res.status_code == 201


def test_pdf_without_text_is_rejected(client, auth):
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)

    res = upload(client, auth, buffer.getvalue(), "scan.pdf")
    assert res.status_code == 400


def test_wrong_file_type_is_rejected(client, auth):
    res = upload(client, auth, b"MZ fake program", "virus.exe")
    assert res.status_code == 400


def test_empty_text_file_is_rejected(client, auth):
    assert upload(client, auth, b"   ", "empty.txt").status_code == 400


def test_too_large_file_is_rejected(client, auth):
    big = b"a" * (5 * 1024 * 1024 + 10)
    assert upload(client, auth, big, "big.txt").status_code == 413


def test_upload_without_a_file(client, auth):
    assert client.post("/api/documents", headers=auth).status_code == 400


def test_delete_document(client, auth):
    did = upload(client, auth, b"Some text here", "a.txt").get_json()["id"]
    assert client.delete(f"/api/documents/{did}", headers=auth).status_code == 200
    assert client.get("/api/documents", headers=auth).get_json() == []


# ---------- Chatting about a document ----------

def test_chat_sends_document_text_to_the_ai(client, auth, fake_ai):
    did = upload(client, auth, b"Cats are great. Dogs are loyal.", "notes.txt").get_json()["id"]
    res = send(client, auth, "What are cats like?", document_id=did)

    assert res.status_code == 200
    assert fake_ai["document"]["name"] == "notes.txt"
    assert "Cats are great" in "\n".join(fake_ai["document"]["excerpts"])


def test_chat_without_document_sends_none(client, auth, fake_ai):
    send(client, auth, "Hello")
    assert fake_ai["document"] is None


def test_chat_with_unknown_document_returns_404(client, auth):
    assert send(client, auth, "Hi", document_id=9999).status_code == 404


def test_users_cannot_use_each_others_documents(client, make_user):
    alice = make_user("alice", "alice@example.com")
    bob = make_user("bob", "bob@example.com")
    did = upload(client, alice, b"Alice's private notes", "private.txt").get_json()["id"]

    assert client.get("/api/documents", headers=bob).get_json() == []
    assert client.delete(f"/api/documents/{did}", headers=bob).status_code == 404
    assert send(client, bob, "What does it say?", document_id=did).status_code == 404


# ---------- Document service (no server needed) ----------

def test_short_text_is_one_chunk():
    chunks = chunk_text("First paragraph.\n\nSecond paragraph.")
    assert len(chunks) == 1


def test_long_text_is_split_into_small_chunks():
    chunks = chunk_text("a" * 2500)
    assert all(len(c) <= 1000 for c in chunks)
    assert "".join(chunks) == "a" * 2500


def test_short_document_is_sent_whole():
    chunks = ["one", "two", "three"]
    assert select_context(chunks, "anything") == chunks


def test_long_document_picks_the_relevant_chunk():
    chunks = ["lorem ipsum " * 90 for _ in range(20)]
    chunks[7] = chunks[7] + " zebra zebra zebra"

    selected = select_context(chunks, "Tell me about the zebra")
    assert chunks[7] in selected
    assert len(selected) <= 5