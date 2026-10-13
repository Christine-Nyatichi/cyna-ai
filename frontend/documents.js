function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

async function loadDocuments() {
  const list = $("doc-list");
  const select = $("doc-select");
  const selected = select.value;

  try {
    const docs = await api("/documents");

    // Popup list
    list.innerHTML = "";
    if (docs.length === 0) {
      list.innerHTML = '<p class="memory-empty">No documents yet.</p>';
    }
    docs.forEach((d) => {
      const row = document.createElement("div");
      row.className = "memory-item";

      const name = document.createElement("span");
      name.className = "doc-name";
      name.textContent = d.filename;

      const size = document.createElement("small");
      size.textContent = formatSize(d.file_size);
      name.appendChild(size);

      const del = document.createElement("button");
      del.textContent = "×";
      del.title = "Delete";
      del.className = "conv-del";
      del.onclick = () => deleteDocument(d.id);

      row.append(name, del);
      list.appendChild(row);
    });

    // Dropdown in the chat header
    select.innerHTML = '<option value="">No document</option>';
    docs.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.id;
      opt.textContent = d.filename;
      select.appendChild(opt);
    });
    if ([...select.options].some((o) => o.value === selected)) select.value = selected;
  } catch (err) {
    list.textContent = err.message;
  }
}

async function uploadDocument() {
  const fileInput = $("doc-file");
  const file = fileInput.files[0];
  if (!file) {
    $("doc-status").textContent = "Choose a file first.";
    return;
  }

  const form = new FormData();
  form.append("file", file);

  $("doc-upload-btn").disabled = true;
  $("doc-status").textContent = "Uploading and reading the file...";

  try {
    const res = await fetch(API + "/documents", {
      method: "POST",
      headers: { Authorization: "Bearer " + token },
      body: form,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || data.msg || "Upload failed");

    fileInput.value = "";
    $("doc-status").textContent = "Uploaded: " + data.filename + ". It is now selected in the chat.";
    await loadDocuments();
    $("doc-select").value = data.id;
  } catch (err) {
    $("doc-status").textContent = "Error: " + err.message;
  } finally {
    $("doc-upload-btn").disabled = false;
  }
}

async function deleteDocument(id) {
  if (!confirm("Delete this document?")) return;
  try {
    await api("/documents/" + id, { method: "DELETE" });
    loadDocuments();
  } catch (err) {
    alert(err.message);
  }
}

$("doc-btn").onclick = () => {
  show($("doc-modal"));
  $("doc-status").textContent = "";
  loadDocuments();
};
$("doc-close").onclick = () => hide($("doc-modal"));
$("doc-upload-btn").onclick = uploadDocument;

// Load the dropdown whenever the chat screen appears (login or auto-login)
new MutationObserver(() => {
  if (!$("app-screen").classList.contains("hidden")) loadDocuments();
}).observe($("app-screen"), { attributes: true, attributeFilter: ["class"] });

if (token) loadDocuments();