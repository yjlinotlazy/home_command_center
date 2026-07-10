const state = {
  apps: [],
  tags: [],
  search: "",
  tag: "",
  status: "",
};

const els = {
  apps: document.querySelector("[data-apps]"),
  count: document.querySelector("[data-count]"),
  empty: document.querySelector("[data-empty]"),
  error: document.querySelector("[data-error]"),
  search: document.querySelector("[data-search]"),
  tag: document.querySelector("[data-tag]"),
  status: document.querySelector("[data-status]"),
};

function statusLabel(status) {
  if (status === "online") return "在线";
  if (status === "offline") return "离线";
  return "未知";
}

function initials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function renderTags(tags) {
  if (!tags.length) return "";
  return `<div class="tags">${tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderApp(app) {
  const media = app.thumbnail
    ? `<img class="thumb" src="${escapeHtml(app.thumbnail)}" alt="">`
    : `<div class="fallback" aria-hidden="true">${escapeHtml(initials(app.name))}</div>`;
  const actionLabel = app.kind === "command" ? "使用" : "打开";

  return `<a class="card" data-card href="${escapeHtml(app.url)}" target="_blank" rel="noopener noreferrer">
    ${media}
    <div class="body">
      <div class="card-head">
        <div>
          <h2 class="name">${escapeHtml(app.name)}</h2>
          <span class="host">${escapeHtml(app.hostname)}</span>
        </div>
        <span class="status ${escapeHtml(app.status)}">${statusLabel(app.status)}</span>
      </div>
      <div class="description">${escapeHtml(app.description || "没有描述。")}</div>
      ${renderTags(app.tags)}
      <span class="open card-action">${actionLabel}</span>
    </div>
  </a>`;
}

function filteredApps() {
  const query = state.search.trim().toLowerCase();
  return state.apps.filter((app) => {
    const matchesSearch =
      !query ||
      [app.name, app.hostname, app.description, app.url].some((value) =>
        String(value || "").toLowerCase().includes(query),
      );
    const matchesTag = !state.tag || app.tags.includes(state.tag);
    const matchesStatus = !state.status || app.status === state.status;
    return matchesSearch && matchesTag && matchesStatus;
  });
}

function render() {
  const apps = filteredApps();
  els.apps.innerHTML = apps.map(renderApp).join("");
  els.count.textContent = `${apps.length} 个应用`;
  els.empty.hidden = apps.length !== 0;
}

function renderTagOptions() {
  for (const tag of state.tags) {
    const option = document.createElement("option");
    option.value = tag;
    option.textContent = tag;
    els.tag.append(option);
  }
}

async function loadApps() {
  try {
    const response = await fetch("/api/apps", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "无法加载应用");

    state.apps = payload.apps;
    state.tags = payload.tags;
    renderTagOptions();
    render();
  } catch (error) {
    els.error.hidden = false;
    els.error.textContent = error.message;
  }
}

els.search.addEventListener("input", (event) => {
  state.search = event.target.value;
  render();
});

els.tag.addEventListener("change", (event) => {
  state.tag = event.target.value;
  render();
});

els.status.addEventListener("change", (event) => {
  state.status = event.target.value;
  render();
});

loadApps();
