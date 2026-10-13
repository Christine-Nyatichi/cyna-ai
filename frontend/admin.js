function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function statCard(label, value) {
  const card = el("div", "stat");
  card.append(el("div", "stat-value", String(value)), el("div", "stat-label", label));
  return card;
}

function adminSection(title) {
  const box = el("div", "admin-section");
  box.appendChild(el("h3", "", title));
  return box;
}

function adminTable(headers, rows) {
  const table = el("table", "admin-table");
  const head = el("tr");
  headers.forEach((h) => head.appendChild(el("th", "", h)));
  table.appendChild(head);

  rows.forEach((cells) => {
    const tr = el("tr");
    cells.forEach((c) => tr.appendChild(el("td", "", String(c))));
    table.appendChild(tr);
  });
  return table;
}

function prettyTime(iso) {
  return iso.replace("T", " ").slice(0, 16);
}

async function checkAdmin() {
  try {
    const me = await api("/auth/me");
    if (me.role === "admin") show($("admin-btn"));
    else hide($("admin-btn"));
  } catch (err) {
    hide($("admin-btn"));
  }
}

async function loadAdmin() {
  const body = $("admin-body");
  body.textContent = "Loading...";

  try {
    const d = await api("/admin/stats");
    body.innerHTML = "";

    // Last 24 hours
    const day = adminSection("Last 24 hours (UTC)");
    const dayGrid = el("div", "stat-grid");
    dayGrid.append(
      statCard("Requests", d.last_24h.requests),
      statCard("Errors", d.last_24h.errors),
      statCard("Active users", d.last_24h.active_users),
      statCard("AI replies", d.last_24h.ai_replies)
    );
    day.appendChild(dayGrid);

    // Totals
    const totals = adminSection("Totals");
    const totalsGrid = el("div", "stat-grid");
    totalsGrid.append(
      statCard("Users", d.totals.users),
      statCard("New users (7 days)", d.totals.new_users_7d),
      statCard("Conversations", d.totals.conversations),
      statCard("Messages", d.totals.messages),
      statCard("Documents", d.totals.documents),
      statCard("Tasks", d.totals.tasks),
      statCard("Memories", d.totals.memories)
    );
    totals.appendChild(totalsGrid);

    // Requests per day
    const chart = adminSection("Requests per day (last 7 days)");
    const max = Math.max(1, ...d.requests_per_day.map((x) => x.requests));
    const bars = el("div", "bars");
    d.requests_per_day.forEach((x) => {
      const col = el("div", "bar-col");
      const area = el("div", "bar-area");
      const bar = el("div", "bar");
      bar.style.height = Math.round((x.requests / max) * 100) + "%";
      area.appendChild(bar);
      col.append(el("small", "", String(x.requests)), area, el("small", "", x.date.slice(5)));
      bars.appendChild(col);
    });
    chart.appendChild(bars);

    // Top endpoints
    const top = adminSection("Most used endpoints (7 days)");
    top.appendChild(
      d.top_endpoints.length
        ? adminTable(["Endpoint", "Requests"], d.top_endpoints.map((e) => [e.endpoint, e.count]))
        : el("p", "memory-empty", "No requests yet.")
    );

    // Recent errors
    const errors = adminSection("Recent errors");
    errors.appendChild(
      d.recent_errors.length
        ? adminTable(
            ["Time (UTC)", "Status", "Endpoint"],
            d.recent_errors.map((e) => [prettyTime(e.created_at), e.status_code, e.endpoint])
          )
        : el("p", "memory-empty", "No errors. Nice.")
    );

    // Recent users
    const users = adminSection("Newest users");
    users.appendChild(
      adminTable(
        ["Username", "Email", "Role", "Joined (UTC)", "Chats"],
        d.recent_users.map((u) => [u.username, u.email, u.role, prettyTime(u.created_at), u.conversations])
      )
    );

    body.append(day, totals, chart, top, errors, users);
  } catch (err) {
    body.textContent = "Error: " + err.message;
  }
}

$("admin-btn").onclick = () => {
  show($("admin-modal"));
  loadAdmin();
};
$("admin-close").onclick = () => hide($("admin-modal"));
$("admin-refresh").onclick = loadAdmin;

// Show the Admin button only for admin accounts, and tidy up on log out
new MutationObserver(() => {
  if ($("app-screen").classList.contains("hidden")) {
    hide($("admin-btn"));
    hide($("admin-modal"));
  } else {
    checkAdmin();
  }
}).observe($("app-screen"), { attributes: true, attributeFilter: ["class"] });

if (token) checkAdmin();