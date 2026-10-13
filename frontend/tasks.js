async function loadTasks() {
  const list = $("task-list");
  try {
    const tasks = await api("/tasks");
    list.innerHTML = "";

    if (tasks.length === 0) {
      list.innerHTML = '<p class="memory-empty">No tasks yet.</p>';
      return;
    }

    tasks.forEach((t) => {
      const row = document.createElement("div");
      row.className = "task-item" + (t.is_completed ? " done" : "");

      const check = document.createElement("input");
      check.type = "checkbox";
      check.checked = t.is_completed;
      check.onchange = () => updateTask(t.id, { is_completed: check.checked });

      const title = document.createElement("span");
      title.textContent = t.title;

      const edit = document.createElement("button");
      edit.textContent = "✎";
      edit.title = "Edit";
      edit.className = "conv-del";
      edit.onclick = () => editTask(t);

      const del = document.createElement("button");
      del.textContent = "×";
      del.title = "Delete";
      del.className = "conv-del";
      del.onclick = () => deleteTask(t.id);

      row.append(check, title, edit, del);
      list.appendChild(row);
    });
  } catch (err) {
    list.textContent = err.message;
  }
}

async function addTask() {
  const input = $("task-input");
  const title = input.value.trim();
  if (!title) return;
  try {
    await api("/tasks", { method: "POST", body: JSON.stringify({ title }) });
    input.value = "";
    loadTasks();
  } catch (err) {
    alert(err.message);
  }
}

async function updateTask(id, changes) {
  try {
    await api("/tasks/" + id, { method: "PATCH", body: JSON.stringify(changes) });
    loadTasks();
  } catch (err) {
    alert(err.message);
  }
}

function editTask(t) {
  const title = prompt("Edit task", t.title);
  if (title === null) return;
  if (!title.trim()) return;
  updateTask(t.id, { title: title.trim() });
}

async function deleteTask(id) {
  if (!confirm("Delete this task?")) return;
  try {
    await api("/tasks/" + id, { method: "DELETE" });
    loadTasks();
  } catch (err) {
    alert(err.message);
  }
}

$("task-btn").onclick = () => {
  show($("task-modal"));
  loadTasks();
};
$("task-close").onclick = () => hide($("task-modal"));
$("task-add-btn").onclick = addTask;
$("task-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") addTask();
});