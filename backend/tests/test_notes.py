import io

from docx import Document as DocxDocument

import routes.notes as notes_routes
from services.ai_service import AIServiceError
from services.notes_service import parse_notes

NOTES = "# Plan\n- first idea\n- second idea\n\nSome closing words."


def export(client, headers, **extra):
    body = {"title": "My plan", "notes": NOTES, "format": "pdf", **extra}
    return client.post("/api/notes/export", json=body, headers=headers)


def docx_text(response):
    doc = DocxDocument(io.BytesIO(response.data))
    return "\n".join(p.text for p in doc.paragraphs)


def test_notes_export_requires_login(client):
    assert client.post("/api/notes/export", json={"notes": "hi"}).status_code == 401


def test_export_pdf(client, auth):
    res = export(client, auth)
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert res.data.startswith(b"%PDF")
    assert 'filename="My-plan.pdf"' in res.headers["Content-Disposition"]


def test_export_docx_contains_the_text(client, auth):
    res = export(client, auth, format="docx")
    assert res.status_code == 200
    assert 'filename="My-plan.docx"' in res.headers["Content-Disposition"]

    text = docx_text(res)
    assert "My plan" in text
    assert "first idea" in text
    assert "Some closing words." in text


def test_empty_notes_are_rejected(client, auth):
    assert export(client, auth, notes="   ").status_code == 400


def test_unknown_format_is_rejected(client, auth):
    assert export(client, auth, format="exe").status_code == 400


def test_very_long_notes_are_rejected(client, auth):
    assert export(client, auth, notes="a" * 20001).status_code == 400


def test_organize_asks_the_ai_to_tidy_the_notes(client, auth, monkeypatch):
    seen = {}

    def fake_generate_reply(messages, mode="general", memories=None, document=None):
        seen["messages"] = messages
        seen["mode"] = mode
        seen["memories"] = memories
        return "# Clean notes\n- tidy point"

    monkeypatch.setattr(notes_routes, "generate_reply", fake_generate_reply)

    res = export(client, auth, format="docx", organize=True)
    assert res.status_code == 200
    assert seen["mode"] == "notes"
    assert seen["memories"] is None
    assert "first idea" in seen["messages"][0]["content"]
    assert "tidy point" in docx_text(res)


def test_organize_failure_returns_503(client, auth, monkeypatch):
    def broken(*args, **kwargs):
        raise AIServiceError("AI is down")

    monkeypatch.setattr(notes_routes, "generate_reply", broken)
    assert export(client, auth, organize=True).status_code == 503


def test_unusual_characters_do_not_break_the_pdf(client, auth):
    res = export(client, auth, notes="Café – “quotes” and an emoji 😀 and 日本語")
    assert res.status_code == 200
    assert res.data.startswith(b"%PDF")


def test_parse_notes_recognises_the_structure():
    blocks = parse_notes("# Title\n## Section\n- a\n  - nested\n1. one\nplain text")
    assert [b[0] for b in blocks] == ["h1", "h2", "bullet", "bullet", "number", "para"]
    assert blocks[3][2] == 1  # the nested bullet is one level in


def test_parse_notes_removes_markdown_marks():
    blocks = parse_notes("**bold** and `code` and [a link](https://example.com)")
    assert blocks[0][1] == "bold and code and a link"