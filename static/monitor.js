const t = (window.__HCC_I18N || { t: (key) => key }).t;
const summary = document.querySelector("[data-monitor-summary]");
const apps = document.querySelector("[data-monitor-apps]");
const error = document.querySelector("[data-monitor-error]");
const updated = document.querySelector("[data-monitor-updated]");

const bytes = (n) => {
  if (n == null) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = n; let index = 0;
  while (value >= 1024 && index < units.length - 1) { value /= 1024; index += 1; }
  return `${value.toFixed(1)} ${units[index]}`;
};
const percent = (n) => n == null ? "—" : `${n.toFixed(1)}%`;
const card = (label, value, detail = "") => `<div class="metric"><span>${label}</span><strong>${value}</strong><small>${detail}</small></div>`;

function render(payload) {
  const m = payload.memory; const d = payload.disk;
  summary.innerHTML = [
    card(t("monitor_host"), payload.host, payload.platform),
    card(t("monitor_cpu"), `${payload.cpu.cores} ${t("monitor_cores")}`, `load ${payload.cpu.load.join(" / ") || "—"}`),
    card(t("monitor_memory"), percent(m.used_percent), `${bytes(m.used)} / ${bytes(m.total)}`),
    card(t("monitor_disk"), percent(d.used_percent), `${bytes(d.used)} / ${bytes(d.total)}`),
    card(t("monitor_uptime"), `${Math.floor(payload.uptime_seconds / 86400)}d ${Math.floor(payload.uptime_seconds % 86400 / 3600)}h`, `Python ${payload.python}`),
  ].join("");
  apps.innerHTML = `<h2>${t("monitor_apps")}</h2><div class="monitor-list">${payload.apps.map((app) => {
    const p = app.process;
    const detail = app.status === "embedded" ? t("monitor_embedded") : p ? `PID ${p.pid} · ${bytes(p.memory)} · ${p.cpu_time}s CPU` : t("monitor_no_process");
    return `<article class="monitor-row"><div><strong>${app.name}</strong><small>${app.port ? `:${app.port}` : t("monitor_builtin")}</small></div><span class="status ${app.status === "embedded" ? "online" : app.status}">${app.status === "embedded" ? t("monitor_embedded") : t(app.status)}</span><p>${detail}</p></article>`;
  }).join("")}</div>`;
  updated.textContent = new Date(payload.updated_at * 1000).toLocaleTimeString();
}

async function load() {
  try { const response = await fetch(`/api/monitor?lang=${encodeURIComponent(window.__HCC_LANG__ || "zh")}`, { cache: "no-store" }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || t("monitor_load_error")); render(payload); }
  catch (e) { error.hidden = false; error.textContent = e.message || t("monitor_load_error"); }
}
load();
setInterval(load, 10000);
