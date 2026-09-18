const t = (window.__HCC_I18N || { t: (key) => key }).t;
const summary = document.querySelector("[data-monitor-summary]");
const apps = document.querySelector("[data-monitor-apps]");
const error = document.querySelector("[data-monitor-error]");
const updated = document.querySelector("[data-monitor-updated]");
const tabs = document.querySelectorAll("[data-monitor-tab]");
const panels = document.querySelectorAll("[data-monitor-panel]");
const statsList = document.querySelector("[data-stats-list]");
const statsError = document.querySelector("[data-stats-error]");
const statsRange = document.querySelector("[data-stats-range]");

const bytes = (n) => {
  if (n == null) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = Number(n); let index = 0;
  while (value >= 1024 && index < units.length - 1) { value /= 1024; index += 1; }
  return `${value.toFixed(1)} ${units[index]}`;
};
const esc = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const card = (label, value, detail = "") => `<div class="metric"><span>${label}</span><strong>${value}</strong><small>${detail}</small></div>`;

function render(payload) {
  const m = payload.memory; const disks = payload.disks || [payload.disk];
  summary.innerHTML = [
    card(t("monitor_host"), payload.host, payload.platform),
    card(t("monitor_cpu"), `${payload.cpu.cores} ${t("monitor_cores")}`, `load ${payload.cpu.load.join(" / ") || "—"}`),
    card(t("monitor_memory"), `${m.used_percent ?? "—"}%`, `RAM ${bytes(m.used)} / ${bytes(m.total)}`),
    ...disks.map((d) => card(`${t("monitor_disk")} ${d.device || ""}`, `${d.used_percent ?? "—"}%`, `${bytes(d.used)} / ${bytes(d.total)}`)),
    card(t("monitor_uptime"), `${Math.floor(payload.uptime_seconds / 86400)}d ${Math.floor(payload.uptime_seconds % 86400 / 3600)}h`, `Python ${payload.python}`),
  ].join("");
  apps.innerHTML = `<h2>${t("monitor_apps")}</h2><div class="monitor-list">${payload.apps.map((app) => {
    const p = app.process;
    const detail = app.status === "embedded" ? t("monitor_embedded") : p ? `PID ${p.pid} · RAM ${bytes(p.memory)} · CPU ${p.cpu_percent}%` : "";
    return `<article class="monitor-row"><div><strong>${esc(app.name)}</strong><small>${app.port ? `:${app.port}` : t("monitor_builtin")}</small></div><span class="status ${esc(app.status === "embedded" ? "online" : app.status)}">${app.status === "embedded" ? t("monitor_embedded") : t(app.status)}</span>${detail ? `<p>${esc(detail)}</p>` : ""}</article>`;
  }).join("")}</div>`;
  updated.textContent = new Date(payload.updated_at * 1000).toLocaleTimeString();
}

async function loadMonitor() {
  try {
    const response = await fetch(`/api/monitor?lang=${encodeURIComponent(window.__HCC_LANG__ || "zh")}`, { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || t("monitor_load_error"));
    render(payload);
  } catch (e) { error.hidden = false; error.textContent = e.message || t("monitor_load_error"); }
}

function statMetric(label, value, detail = "") { return `<div class="metric"><span>${label}</span><strong>${value}</strong><small>${detail}</small></div>`; }

function renderStats(payload, app) {
  const u = payload.usage; const g = payload.git;
  const dev = g.available
    ? `${g.commits_30d} ${t("monitor_commits")} · ${g.active_days_7d} ${t("monitor_dev_days")}`
    : t("monitor_git_unavailable");
  const routes = u.top_routes.map((item) => `<li><code>${esc(item.route)}</code><span>${item.requests}</span></li>`).join("") || `<li>${t("monitor_no_data")}</li>`;
  return `<article class="monitor-stat-card"><header><div><h2>${esc(app.name)}</h2><small>${esc(app.id)}</small></div><span class="status ${g.available ? "online" : "unknown"}">${g.available ? t("monitor_git_ready") : t("monitor_git_unavailable")}</span></header><div class="monitor-stat-grid">${statMetric(t("monitor_requests"), u.requests, `${u.active_days} ${t("monitor_active_days")}`)}${statMetric(t("monitor_errors"), u.error_requests, `${Object.keys(u.methods).length} ${t("monitor_methods")}`)}${statMetric(t("monitor_traffic"), bytes(u.request_bytes + u.response_bytes), `${bytes(u.request_bytes)} in · ${bytes(u.response_bytes)} out`)}${statMetric(t("monitor_latency"), `${u.average_latency_ms} ms`)}${statMetric(t("monitor_commits_30d"), g.available ? g.commits_30d : "—", dev)}${statMetric(t("monitor_since_commit"), g.available && g.days_since_commit != null ? `${g.days_since_commit}d` : "—", g.available ? `${g.branch} · ${g.dirty ? t("monitor_dirty") : t("monitor_clean")}` : "")}</div><div class="monitor-stat-detail"><div><strong>${t("monitor_top_routes")}</strong><ul>${routes}</ul></div><div><strong>${t("monitor_repo")}</strong><p>${g.available ? `${esc(g.path)}<br>${bytes(g.working_tree_bytes)} working · ${bytes(g.git_bytes)} .git` : t("monitor_git_unavailable")}</p></div></div></article>`;
}

async function loadStats() {
  statsError.hidden = true;
  statsList.innerHTML = `<p>${t("monitor_loading")}</p>`;
  try {
    const appsResponse = await fetch(`/api/apps?lang=${encodeURIComponent(window.__HCC_LANG__ || "zh")}`, { cache: "no-store" });
    const appPayload = await appsResponse.json();
    if (!appsResponse.ok) throw new Error(appPayload.error || t("monitor_stats_load_error"));
    const candidates = appPayload.apps.filter((app) => app.id !== "system-monitor");
    const results = await Promise.all(candidates.map(async (app) => {
      const response = await fetch(`/api/stats?app_id=${encodeURIComponent(app.id)}&days=${statsRange.value}`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || t("monitor_stats_load_error"));
      return renderStats(payload, app);
    }));
    statsList.innerHTML = results.join("") || `<p>${t("monitor_no_data")}</p>`;
  } catch (e) { statsError.hidden = false; statsError.textContent = e.message || t("monitor_stats_load_error"); statsList.replaceChildren(); }
}

function showTab(name) {
  tabs.forEach((tab) => { const active = tab.dataset.monitorTab === name; tab.classList.toggle("active", active); tab.setAttribute("aria-selected", String(active)); });
  panels.forEach((panel) => { panel.hidden = panel.dataset.monitorPanel !== name; });
  if (name === "stats") loadStats();
  window.location.hash = name;
}

tabs.forEach((tab) => tab.addEventListener("click", () => showTab(tab.dataset.monitorTab)));
statsRange.addEventListener("change", loadStats);
showTab(window.location.hash === "#stats" ? "stats" : "overview");
loadMonitor();
