const API = "http://127.0.0.1:5001/api";

let token = localStorage.getItem("nova_token");
let currentConversationId = null;
let isRegister = false;

const $ = (id) => document.getElementById(id);
const show = (el) => el.classList.remove("hidden");
const hide = (el) => el.classList.add("hidden");

// ---------- API helper ----------
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = "Bearer " + token;

  const res = await fetch(API + path, { ...options, headers });
  const data = await res.json().catch(() => ({}));

  if (res.status === 401 && token) {
    logout();
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) throw new Error(data.error || data.msg || "Request failed");
  return data;
}

// ---------- Auth ----------
function setAuthMode(register) {
  isRegister = register;
  $("username").classList.toggle("hidden", !register);
  $("auth-btn").textContent = register ? "Create account" : "Log in";
  $("auth-subtitle").textContent = register ? "Create your account" : "Log in to continue";
  $("switch-text").textContent = register ? "Already have an account?" : "No account?";
  $("switch-link").textContent = register ? "Log in" : "Register";
  $("auth-error").textContent = "";
}

async function submitAuth() {
  const username = $("username").value.trim();
  const email = $("email").value.trim();
  const password = $("password").value;
  $("auth-error").textContent = "";

  try {
    if (isRegister) {
      await api("/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, email, password }),
      });
    }
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    token = data.token;
    localStorage.setItem("nova_token", token);
    $("password").value = "";
    enterApp();
  } catch (err) {
    $("auth-error").textContent = err.message;
  }
}

function enterApp() {
  hide($("auth-screen"));
  show($("app-screen"));
  newChat();
}

function logout() {
  token = null;
  localStorage.removeItem("nova_token");
  currentConversationId = null;
  hide($("memory-modal"));
  hide($("task-modal"));
  hide($("doc-modal"));
  hide($("app-screen"));
  show($("auth-screen"));
}

// ---------- Conversations ----------
async function loadConversations() {
  const search = $("search").value.trim();
  try {
    const list = await api("/conversations" + (search ? "?search=" + encodeURIComponent(search) : ""));
    const box = $("conversation-list");
    box.innerHTML = "";

    list.forEach((c) => {
      const row = document.createElement("div");
      row.className = "conv" + (c.id === currentConversationId ? " active" : "");
      row.title = "Double-click to rename";
      row.onclick = () => openConversation(c.id);
      row.ondblclick = () => renameConversation(c);

      const title = document.createElement("span");
      title.textContent = c.title;

      const del = document.createElement("button");
      del.textContent = "×";
      del.className = "conv-del";
      del.onclick = (e) => {
        e.stopPropagation();
        deleteConversation(c.id);
      };

      row.append(title, del);
      box.appendChild(row);
    });
  } catch (err) {
    console.error(err);
  }
}

async function openConversation(id) {
  try {
    const c = await api("/conversations/" + id);
    currentConversationId = c.id;
    $("chat-title").textContent = c.title;
    $("mode").value = c.mode;
    $("messages").innerHTML = "";
    c.messages.forEach((m) => {
      const bubble = addMessage(m.role, m.content);
      if (m.role === "assistant") addMessageActions(bubble);
    });
    loadConversations();
  } catch (err) {
    console.error(err);
  }
}

async function renameConversation(c) {
  const title = prompt("Rename chat", c.title);
  if (!title || !title.trim()) return;
  try {
    await api("/conversations/" + c.id, {
      method: "PATCH",
      body: JSON.stringify({ title: title.trim() }),
    });
    if (c.id === currentConversationId) $("chat-title").textContent = title.trim();
    loadConversations();
  } catch (err) {
    alert(err.message);
  }
}

async function deleteConversation(id) {
  if (!confirm("Delete this chat?")) return;
  try {
    await api("/conversations/" + id, { method: "DELETE" });
    if (id === currentConversationId) newChat();
    else loadConversations();
  } catch (err) {
    alert(err.message);
  }
}

function newChat() {
  currentConversationId = null;
  $("chat-title").textContent = "New chat";
  $("messages").innerHTML = "";
  addMessage("assistant", "Hi, I'm CYNA. How can I help?");
  loadConversations();
}

// ---------- Messages ----------
function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = text;
  $("messages").appendChild(div);
  $("messages").scrollTop = $("messages").scrollHeight;
  return div;
}

// The most recent real answer from CYNA (not the greeting or a status message)
function lastAnswerBubble() {
  const answers = document.querySelectorAll("#messages .msg.assistant[data-answer]");
  return answers.length ? answers[answers.length - 1] : null;
}

// A title for the document: the first heading, or the topic you asked about
function titleFor(bubble) {
  const heading = bubble.textContent.match(/^#{1,3}\s+(.+)$/m);
  if (heading) return heading[1].trim();

  const asked = bubble.previousElementSibling;
  if (asked && asked.classList.contains("user")) {
    const about = asked.textContent.match(/\babout\s+(.+?)[.?!\s]*$/i);
    if (about) return about[1].trim().slice(0, 60);
  }
  return "CYNA notes";
}

// Does this message ask for a PDF or Word file? Returns ["pdf"], ["docx"], both, or null.
function fileRequest(text) {
  const t = text.toLowerCase();
  const wantsPdf = /\bpdf\b/.test(t);
  const wantsWord = /\b(word|docx?)\b/.test(t);
  if (!wantsPdf && !wantsWord) return null;

  const hasVerb = /\b(turn|convert|make|save|export|download|put|change|create|give|send)\b/.test(t);
  const refersBack = /\b(it|this|that|these|those|them|notes|answer)\b/.test(t);
  const isShort = t.trim().split(/\s+/).length <= 6;
  if (!hasVerb || !(refersBack || isShort)) return null;

  const formats = [];
  if (wantsPdf) formats.push("pdf");
  if (wantsWord) formats.push("docx");
  return formats;
}

// Makes the file(s) from CYNA's last answer. The server keeps the files and
// saves your request and CYNA's "Done!" note in this chat.
async function createFilesFromAnswer(bubble, formats, command) {
  const label = formats.map((f) => (f === "pdf" ? "PDF" : "Word document")).join(" and ");
  const status = addMessage("system", "Creating your " + label + "...");

  try {
    const data = await api("/notes/command", {
      method: "POST",
      body: JSON.stringify({
        conversation_id: currentConversationId,
        command,
        notes: bubble.textContent,
        title: titleFor(bubble),
        formats,
      }),
    });

    for (const file of data.files) {
      await downloadStoredFile(file.id, file.filename);
    }
    status.textContent = data.message;
    loadConversations();
  } catch (err) {
    status.textContent = "Sorry, I could not create the file: " + err.message;
  }
}

// "Save as PDF" and "Save as Word" buttons under a CYNA answer
function addMessageActions(bubble) {
  bubble.dataset.answer = "1";

  const bar = document.createElement("div");
  bar.className = "msg-actions";

  [["PDF", "pdf"], ["Word", "docx"]].forEach(([label, format]) => {
    const btn = document.createElement("button");
    btn.textContent = "Save as " + label;

    btn.onclick = async () => {
      btn.disabled = true;
      btn.textContent = "Creating...";
      try {
        await downloadNotesFile({ title: titleFor(bubble), notes: bubble.textContent, format });
      } catch (err) {
        alert(err.message);
      }
      btn.textContent = "Save as " + label;
      btn.disabled = false;
    };

    bar.appendChild(btn);
  });

  bubble.after(bar);
  $("messages").scrollTop = $("messages").scrollHeight;
}

async function sendMessage() {
  const input = $("message-input");
  const text = input.value.trim();
  if (!text) return;

  // "Turn it into a PDF / Word document": handled here, no AI needed
  const formats = fileRequest(text);
  if (formats) {
    input.value = "";
    addMessage("user", text);

    const bubble = lastAnswerBubble();
    if (!bubble || !currentConversationId) {
      addMessage(
        "system",
        "I don't have any notes to turn into a file yet. Ask me to write some first, for example: Make notes about nouns."
      );
      return;
    }

    $("send-btn").disabled = true;
    await createFilesFromAnswer(bubble, formats, text);
    $("send-btn").disabled = false;
    input.focus();
    return;
  }

  input.value = "";
  addMessage("user", text);
  const reply = addMessage("assistant", "...");
  $("send-btn").disabled = true;

  let answer = "";

  try {
    const res = await fetch(API + "/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
      },
      body: JSON.stringify({
        message: text,
        conversation_id: currentConversationId,
        mode: $("mode").value,
        document_id: $("doc-select").value || null,
      }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        logout();
        throw new Error("Session expired. Please log in again.");
      }
      throw new Error(data.error || data.msg || "Request failed");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finished = false;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop(); // keep the unfinished part for the next round

      for (const raw of events) {
        if (!raw.startsWith("data: ")) continue;
        const event = JSON.parse(raw.slice(6));

        if (event.type === "token") {
          answer += event.text;
          reply.textContent = answer;
          $("messages").scrollTop = $("messages").scrollHeight;
        } else if (event.type === "error") {
          throw new Error(event.error);
        } else if (event.type === "done") {
          finished = true;
          if (!currentConversationId) $("chat-title").textContent = text.slice(0, 50);
          currentConversationId = event.conversation_id;
          addMessageActions(reply);
          loadConversations();

          // Refresh the memory list if it is open (a "remember ..." message may have added one)
          if (!$("memory-modal").classList.contains("hidden")) loadMemories();
        }
      }
    }

    if (!finished) throw new Error("The reply was interrupted. Please try again.");
  } catch (err) {
    reply.textContent = answer
      ? answer + "\n\n[Error: " + err.message + "]"
      : "Error: " + err.message;
  } finally {
    $("send-btn").disabled = false;
    input.focus();
  }
}

// ---------- Memory ----------
async function loadMemories() {
  const list = $("memory-list");
  try {
    const items = await api("/memories");
    list.innerHTML = "";

    if (items.length === 0) {
      list.innerHTML = '<p class="memory-empty">Nothing saved yet.</p>';
      return;
    }

    items.forEach((m) => {
      const row = document.createElement("div");
      row.className = "memory-item";

      const text = document.createElement("span");
      text.textContent = m.content;

      const del = document.createElement("button");
      del.textContent = "×";
      del.className = "conv-del";
      del.onclick = async () => {
        try {
          await api("/memories/" + m.id, { method: "DELETE" });
          loadMemories();
        } catch (err) {
          alert(err.message);
        }
      };

      row.append(text, del);
      list.appendChild(row);
    });
  } catch (err) {
    list.textContent = err.message;
  }
}

async function addMemory() {
  const input = $("memory-input");
  const content = input.value.trim();
  if (!content) return;
  try {
    await api("/memories", { method: "POST", body: JSON.stringify({ content }) });
    input.value = "";
    loadMemories();
  } catch (err) {
    alert(err.message);
  }
}

async function clearMemories() {
  if (!confirm("Delete everything CYNA remembers?")) return;
  try {
    await api("/memories", { method: "DELETE" });
    loadMemories();
  } catch (err) {
    alert(err.message);
  }
}

// ---------- Events ----------
$("auth-btn").onclick = submitAuth;
$("password").addEventListener("keydown", (e) => {
  if (e.key === "Enter") submitAuth();
});
$("switch-link").onclick = (e) => {
  e.preventDefault();
  setAuthMode(!isRegister);
};
$("logout-btn").onclick = logout;
$("new-chat-btn").onclick = newChat;
$("send-btn").onclick = sendMessage;
$("message-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
$("search").addEventListener("input", loadConversations);

$("memory-btn").onclick = () => {
  show($("memory-modal"));
  loadMemories();
};
$("memory-close").onclick = () => hide($("memory-modal"));
$("memory-add-btn").onclick = addMemory;
$("memory-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") addMemory();
});
$("memory-clear").onclick = clearMemories;

// Auto-login if a saved token exists
if (token) enterApp();