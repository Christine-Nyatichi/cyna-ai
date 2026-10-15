async function exportConversation(format) {
  if (!currentConversationId) {
    alert("Send a message first, then you can export the chat.");
    return;
  }

  try {
    const res = await fetch(
      API + "/conversations/" + currentConversationId + "/export?format=" + format,
      { headers: { Authorization: "Bearer " + token } }
    );

    if (res.status === 401) {
      logout();
      return;
    }
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || "Export failed");
    }

    const blob = await res.blob();
    const name =
      $("chat-title").textContent.replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) ||
      "conversation";

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name + "." + format;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(err.message);
  }
}

$("export-select").onchange = (e) => {
  const format = e.target.value;
  e.target.value = ""; // reset the dropdown so it can be used again
  if (format) exportConversation(format);
};