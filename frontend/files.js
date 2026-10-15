function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// Downloads a file that CYNA created earlier (also used by the chat command in app.js)
async function downloadStoredFile(id, filename) {
  const res = await fetch(API + "/files/" + id + "/download", {
    headers: { Authorization: "Bearer " + token },
  });

  if (res.status === 401) {
    logout();
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "Could not download the file");
  }

  saveBlob(await res.blob(), filename);
}

async function loadFiles() {
  const list = $("files-list");
  try {
    const files = await api("/files");
    list.innerHTML = "";

    if (files.length === 0) {
      list.innerHTML =
        '<p class="memory-empty">No files yet. Ask CYNA for notes, then say "turn it into a PDF".</p>';
      return;
    }

    files.forEach((f) => {
      const row = document.createElement("div");
      row.className = "memory-item";

      const name = document.createElement("span");
      name.className = "doc-name";
      name.textContent = f.filename;

      const info = document.createElement("small");
      info.textContent = f.created_at.replace("T", " ").slice(0, 16) + " · " + formatSize(f.size);
      name.appendChild(info);

      const download = document.createElement("button");
      download.textContent = "Download";
      download.className = "file-btn";
      download.onclick = async () => {
        try {
          await downloadStoredFile(f.id, f.filename);
        } catch (err) {
          alert(err.message);
        }
      };

      const del = document.createElement("button");
      del.textContent = "×";
      del.title = "Delete";
      del.className = "conv-del";
      del.onclick = async () => {
        if (!confirm("Delete " + f.filename + "?")) return;
        try {
          await api("/files/" + f.id, { method: "DELETE" });
          loadFiles();
        } catch (err) {
          alert(err.message);
        }
      };

      row.append(name, download, del);
      list.appendChild(row);
    });
  } catch (err) {
    list.textContent = err.message;
  }
}

$("files-btn").onclick = () => {
  show($("files-modal"));
  loadFiles();
};
$("files-close").onclick = () => hide($("files-modal"));

// Close the popup if the user logs out
new MutationObserver(() => {
  if ($("app-screen").classList.contains("hidden")) hide($("files-modal"));
}).observe($("app-screen"), { attributes: true, attributeFilter: ["class"] });