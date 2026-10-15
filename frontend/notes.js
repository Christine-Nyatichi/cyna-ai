// Uses lastAnswerBubble() from app.js: CYNA's last real answer
function lastAnswerText() {
  const bubble = lastAnswerBubble();
  return bubble ? bubble.textContent : "";
}

function setNotesBusy(busy) {
  ["notes-write", "notes-pdf", "notes-docx", "notes-last"].forEach((id) => {
    $(id).disabled = busy;
  });
}

function safeName(text) {
  return (text || "").replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "notes";
}

// Asks the server for a PDF or Word file and saves it. Also used by the
// "Save as PDF / Word" buttons and the "turn it into a PDF" chat command (see app.js).
async function downloadNotesFile({ title = "", notes = "", topic = "", format, organize = false }) {
  const res = await fetch(API + "/notes/export", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + token,
    },
    body: JSON.stringify({ title, notes, topic, format, organize }),
  });

  if (res.status === 401) {
    logout();
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || data.msg || "Could not create the file");
  }

  const blob = await res.blob();
  const filename = safeName(title || topic) + "." + format;

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);

  return filename;
}

// "Write notes": CYNA writes notes on the topic and shows them so you can edit them
async function writeNotes() {
  const topic = $("notes-topic").value.trim();
  const status = $("notes-status");

  if (!topic) {
    status.textContent = "Type a topic first, for example: nouns";
    return;
  }

  setNotesBusy(true);
  status.textContent = "CYNA is writing your notes...";

  try {
    const data = await api("/notes/generate", {
      method: "POST",
      body: JSON.stringify({ topic }),
    });
    $("notes-text").value = data.notes;
    if (!$("notes-title").value.trim()) $("notes-title").value = data.title;
    status.textContent = "Notes written. Edit them if you like, then download.";
  } catch (err) {
    status.textContent = "Error: " + err.message;
  } finally {
    setNotesBusy(false);
  }
}

// Download buttons: use the notes in the box, or let CYNA write them from the topic
async function downloadFromPopup(format) {
  const notes = $("notes-text").value.trim();
  const topic = $("notes-topic").value.trim();
  const status = $("notes-status");

  if (!notes && !topic) {
    status.textContent = "Type a topic for CYNA to write about, or paste your own notes.";
    return;
  }

  const organize = $("notes-organize").checked;

  setNotesBusy(true);
  status.textContent = !notes
    ? "CYNA is writing your notes and creating the file..."
    : organize
    ? "CYNA is organizing your notes..."
    : "Creating your file...";

  try {
    const file = await downloadNotesFile({
      title: $("notes-title").value.trim(),
      notes,
      topic: notes ? "" : topic,
      format,
      organize,
    });
    status.textContent = "Downloaded " + file;
  } catch (err) {
    status.textContent = "Error: " + err.message;
  } finally {
    setNotesBusy(false);
  }
}

$("notes-btn").onclick = () => {
  show($("notes-modal"));
  $("notes-status").textContent = "";
};
$("notes-close").onclick = () => hide($("notes-modal"));
$("notes-write").onclick = writeNotes;
$("notes-topic").addEventListener("keydown", (e) => {
  if (e.key === "Enter") writeNotes();
});
$("notes-pdf").onclick = () => downloadFromPopup("pdf");
$("notes-docx").onclick = () => downloadFromPopup("docx");
$("notes-last").onclick = () => {
  const text = lastAnswerText();
  if (!text) {
    $("notes-status").textContent = "There is no answer to copy yet.";
    return;
  }
  $("notes-text").value = text;
  $("notes-status").textContent = "Copied CYNA's last answer into the box.";
};

// Close the popup if the user logs out
new MutationObserver(() => {
  if ($("app-screen").classList.contains("hidden")) hide($("notes-modal"));
}).observe($("app-screen"), { attributes: true, attributeFilter: ["class"] });