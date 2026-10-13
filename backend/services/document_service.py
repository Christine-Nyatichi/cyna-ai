import re

from pypdf import PdfReader
from docx import Document as DocxDocument

STOPWORDS = {
    "the", "and", "for", "are", "was", "were", "what", "which", "who", "how", "why",
    "when", "where", "does", "did", "this", "that", "these", "those", "with", "from",
    "about", "into", "have", "has", "had", "can", "could", "would", "should", "you",
    "your", "tell", "give", "show", "please", "document", "file",
}


def extract_text(stream, ext):
    """Read plain text out of a pdf, docx or txt file."""
    if ext == "txt":
        return stream.read().decode("utf-8", errors="ignore")

    if ext == "pdf":
        reader = PdfReader(stream)
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)

    if ext == "docx":
        doc = DocxDocument(stream)
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

    raise ValueError("unsupported file type")


def chunk_text(text, size=1000):
    """Split text into pieces of roughly `size` characters, keeping paragraphs together."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, current = [], ""

    for p in paragraphs:
        while len(p) > size:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(p[:size])
            p = p[size:]
        if not p:
            continue
        if current and len(current) + len(p) + 2 > size:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n\n{p}" if current else p

    if current:
        chunks.append(current)
    return chunks


def select_context(chunks, question, max_chars=12000, top_k=5):
    """Pick the chunks most relevant to the question.

    Short documents are sent whole. Long ones are scored by keyword matches.
    """
    if sum(len(c) for c in chunks) <= max_chars:
        return chunks

    words = {
        w for w in re.findall(r"[a-z0-9]+", question.lower())
        if len(w) > 2 and w not in STOPWORDS
    }

    scored = []
    for i, c in enumerate(chunks):
        lower = c.lower()
        scored.append((sum(lower.count(w) for w in words), i))
    scored.sort(key=lambda x: (-x[0], x[1]))

    best = [i for score, i in scored[:top_k] if score > 0]
    if not best:
        best = list(range(min(top_k, len(chunks))))
    return [chunks[i] for i in sorted(best)]