const toolId = window.__COMMAND_TOOL_ID__;
const form = document.querySelector("[data-tool-form]");
const fields = document.querySelector("[data-tool-fields]");
const output = document.querySelector("[data-tool-output]");
const statusBox = document.querySelector("[data-tool-status]");
const errorBox = document.querySelector("[data-tool-error]");
const submit = document.querySelector("[data-tool-submit]");
const files = document.querySelector("[data-tool-files]");
const dakaPane = document.querySelector("[data-tool-daka]");
const mobileOutputQuery = window.matchMedia("(max-width: 720px)");
const toolLayout = window.__COMMAND_TOOL_LAYOUT__ || "";
const i18n = window.__HCC_I18N || {
  currentLang: () => (window.__HCC_LANG__ === "en" ? "en" : "zh"),
  t: (key, value) => {
    if (key === "open") return "打开";
    if (key === "tool_load_error") return "无法加载工具";
    if (key === "tool_run_error") return "工具运行失败";
    if (key === "no_output") return "（没有输出）";
    if (key === "load_daka_error") return "无法加载打卡数据";
    if (key === "generate_report_error") return "无法生成报告";
    if (key === "checkin_failed") return "打卡失败";
    if (key === "checkin_done") return "打卡完成";
    if (key === "date") return "日期";
    if (key === "report_task_summary") return "生成任务汇总";
    if (key === "report_resolution_summary") return "生成愿望汇总";
    if (key === "report_task_summary_done") return "任务汇总已生成。";
    if (key === "report_resolution_summary_done") return "愿望汇总已生成。";
    if (key === "report_task_summary_loading") return "正在生成任务汇总。";
    if (key === "report_resolution_summary_loading") return "正在生成愿望汇总。";
    if (key === "no_daka_items") return "还没有打卡项目。";
    if (key === "no_data") return "没有可显示的数据。";
    if (key === "today_checked") return "今天已打卡";
    if (key === "click_to_checkin") return "点击打卡";
    if (key === "count_items") return `${value} 项`;
    if (key === "total_checkins") return `累计 ${value} 次`;
    if (key === "annual_progress") return "年度进度";
    if (key === "weekly_progress") return "周度进度";
    if (key === "day_short") return "日";
    if (key === "week_short") return "周";
    if (key === "daka_task_summary") return "任务汇总";
    if (key === "daka_resolution_summary") return "愿望汇总";
    if (key === "task_level") return "任务级别";
    if (key === "resolution_level") return "愿望级别";
    return key;
  },
};
const lang = i18n.currentLang();
const t = i18n.t;
let lastOutputText = "";
let currentDakaDate = "";
let currentDakaReport = "";
const DAKA_PALETTES = [
  "#f7eef7",
  "#eef6fb",
  "#f4f7ea",
  "#fbf3ea",
  "#eef7f2",
  "#f2f1fb",
  "#fff0f2",
  "#eef8f8",
];

const REPORT_COLORS = [
  "#d44f4f",
  "#3f9d57",
  "#b58900",
  "#4b73c6",
  "#a44cc0",
  "#1b9aaa",
  "#f26b5e",
  "#56c271",
  "#5f8fff",
];

const ANSI_COLOR_MAP = {
  "\u001b[31m": "#d44f4f",
  "\u001b[32m": "#3f9d57",
  "\u001b[33m": "#b58900",
  "\u001b[34m": "#4b73c6",
  "\u001b[35m": "#a44cc0",
  "\u001b[36m": "#1b9aaa",
  "\u001b[91m": "#f26b5e",
  "\u001b[92m": "#56c271",
  "\u001b[94m": "#5f8fff",
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function ansiToHtml(value) {
  const colors = {
    "31": "ansi-red",
    "32": "ansi-green",
    "34": "ansi-blue",
    "35": "ansi-purple",
    "38;5;208": "ansi-orange",
  };
  let html = "";
  let open = false;
  let cursor = 0;
  const pattern = /\x1b\[([0-9;]*)m/g;
  for (const match of value.matchAll(pattern)) {
    html += escapeHtml(value.slice(cursor, match.index));
    const code = match[1] || "0";
    if (open) {
      html += "</span>";
      open = false;
    }
    if (code !== "0") {
      const className = colors[code];
      if (className) {
        html += `<span class="${className}">`;
        open = true;
      }
    }
    cursor = match.index + match[0].length;
  }
  html += escapeHtml(value.slice(cursor));
  if (open) html += "</span>";
  return html;
}

function formatOutputText(value) {
  if (toolId !== "eat-what" || !mobileOutputQuery.matches) {
    return value;
  }
  return oneColumnEatWhatMenu(value);
}

function oneColumnEatWhatMenu(value) {
  const lines = value.split("\n");
  const result = [];
  let inMenu = false;
  let seenMenuDivider = false;

  for (const line of lines) {
    if (line.includes("这周将就吃：")) {
      inMenu = true;
      seenMenuDivider = false;
      result.push(line);
      continue;
    }

    if (inMenu && line.trim() === "-") {
      result.push(line);
      if (seenMenuDivider) {
        inMenu = false;
      } else {
        seenMenuDivider = true;
      }
      continue;
    }

    if (inMenu && seenMenuDivider) {
      const parts = line
        .split(/ {2,}(?=\x1b\[38;5;208m\d+\.\x1b\[0m )/)
        .map((part) => part.trimEnd())
        .filter(Boolean);
      result.push(...(parts.length ? parts : [line]));
      continue;
    }

    result.push(line);
  }

  return result.join("\n");
}

function renderOutputText(text) {
  output.innerHTML = ansiToHtml(formatOutputText(text));
}

function showError(message) {
  errorBox.hidden = false;
  errorBox.textContent = message;
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
}

function showStatus(message) {
  statusBox.hidden = false;
  statusBox.classList.add("tool-status");
  statusBox.textContent = message;
}

function clearStatus() {
  statusBox.hidden = true;
  statusBox.classList.remove("tool-status");
  statusBox.textContent = "";
}

function colorForResolution(colorValue, index) {
  if (colorValue) return colorValue;
  return REPORT_COLORS[index % REPORT_COLORS.length];
}

function cssColorForResolution(colorValue, index) {
  if (ANSI_COLOR_MAP[colorValue]) return ANSI_COLOR_MAP[colorValue];
  return colorForResolution(colorValue, index);
}

function pastelForName(name, index) {
  if (!name) return DAKA_PALETTES[index % DAKA_PALETTES.length];
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  }
  return DAKA_PALETTES[hash % DAKA_PALETTES.length];
}

function fieldHtml(arg) {
  const attrs = [
    `name="${escapeHtml(arg.name)}"`,
    `data-kind="${escapeHtml(arg.kind)}"`,
    `maxlength="${Number(arg.max_length) || 200}"`,
  ];
  if (arg.required) attrs.push("required");
  if (arg.placeholder) attrs.push(`placeholder="${escapeHtml(arg.placeholder)}"`);
  if (arg.pattern) attrs.push(`pattern="${escapeHtml(arg.pattern)}"`);

  let control = "";
  if (arg.kind === "textarea") {
    control = `<textarea ${attrs.join(" ")}>${escapeHtml(arg.default || "")}</textarea>`;
  } else if (arg.kind === "date") {
    control = `<input type="date" value="${escapeHtml(arg.default || "")}" ${attrs.join(" ")}>`;
  } else if (arg.kind === "select") {
    const options = arg.choices
      .map((choice) => {
        const selected = choice === arg.default ? " selected" : "";
        return `<option value="${escapeHtml(choice)}"${selected}>${escapeHtml(choice)}</option>`;
      })
      .join("");
    control = `<select ${attrs.join(" ")}>${options}</select>`;
  } else {
    control = `<input type="text" value="${escapeHtml(arg.default || "")}" ${attrs.join(" ")}>`;
  }

  return `<label class="tool-field">
    <span>${escapeHtml(arg.label)}</span>
    ${control}
    ${arg.help ? `<small>${escapeHtml(arg.help)}</small>` : ""}
  </label>`;
}

function sanitizeValue(input) {
  return input.value.trim();
}

function renderFields(args) {
  const htmlByName = new Map(args.map((arg) => [arg.name, fieldHtml(arg)]));
  const slots = fields.querySelectorAll("[data-tool-slot]");

  if (toolLayout === "chinese-practice" && slots.length) {
    for (const slot of slots) {
      slot.innerHTML = htmlByName.get(slot.dataset.toolSlot) || "";
    }
    return;
  }

  fields.innerHTML = args.map(fieldHtml).join("");
}

async function loadTool() {
  const url = new URL(`/api/tools/${encodeURIComponent(toolId)}`, window.location.origin);
  if (lang === "en") url.searchParams.set("lang", lang);
  const response = await fetch(url.toString(), { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || t("tool_load_error"));

  document.querySelector("[data-tool-title]").textContent = payload.name;
  document.querySelector("[data-tool-description]").textContent = payload.description;

  if (payload.kind === "daka") {
    form.hidden = true;
    output.hidden = true;
    files.hidden = true;
    clearError();
    clearStatus();
    currentDakaReport = "";
    renderDakaTool(payload);
    return;
  }

  renderFields(payload.args);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  output.textContent = "";
  files.replaceChildren();
  submit.disabled = true;

  try {
    const payload = {};
    for (const input of form.querySelectorAll("input, textarea, select")) {
      payload[input.name] = sanitizeValue(input);
    }

    const url = new URL(`/api/tools/${encodeURIComponent(toolId)}/run`, window.location.origin);
    if (lang === "en") url.searchParams.set("lang", lang);
    const response = await fetch(url.toString(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || t("tool_run_error"));

    lastOutputText = result.stdout || result.stderr || t("no_output");
    renderOutputText(lastOutputText);
    output.classList.toggle("failed", !result.ok);
    renderFiles(result.files || []);
  } catch (error) {
    showError(error.message);
  } finally {
    submit.disabled = false;
  }
});

loadTool().catch((error) => showError(error.message));

mobileOutputQuery.addEventListener("change", () => {
  if (lastOutputText) {
    renderOutputText(lastOutputText);
  }
});

function renderFiles(generatedFiles) {
  files.replaceChildren();
  files.hidden = generatedFiles.length === 0;
  if (!generatedFiles.length) return;

  for (const file of generatedFiles) {
    const link = document.createElement("a");
    link.className = "generated-file";
    link.href = file.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = `${t("open")} ${file.name}`;
    files.append(link);
  }
}

async function loadDakaState(dateValue, statusMessage = "") {
  currentDakaDate = dateValue || currentDakaDate || "";
  if (!statusMessage) {
    clearStatus();
  }
  const url = new URL("/api/tools/daka", window.location.origin);
  if (lang === "en") url.searchParams.set("lang", lang);
  if (currentDakaDate) url.searchParams.set("date", currentDakaDate);
  const response = await fetch(url.toString(), { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || t("load_daka_error"));
  renderDakaTool(payload);
  if (currentDakaReport) {
    const reportPane = dakaPane.querySelector("[data-daka-report-panel]");
    const reportStatus = dakaPane.querySelector("[data-daka-report-status]");
    await loadDakaReport(currentDakaReport, reportPane, reportStatus, false);
  }
  if (statusMessage) {
    showStatus(statusMessage);
  }
}

function renderDakaTool(payload) {
  clearError();
  files.hidden = true;
  output.hidden = true;
  form.hidden = true;
  dakaPane.hidden = false;
  currentDakaDate = payload.date;

  dakaPane.innerHTML = `
    <div class="daka-controls">
      <label class="tool-field daka-date-field">
        <span>${t("date")}</span>
        <input type="date" data-daka-date value="${escapeHtml(payload.date)}">
      </label>
    </div>
    <div class="daka-grid" data-daka-grid></div>
    <div class="daka-bottom">
      <div class="daka-actions">
        <button type="button" class="open daka-action" data-daka-report-button="summary">${t("report_task_summary")}</button>
        <button type="button" class="open daka-action" data-daka-report-button="resolution-summary">${t("report_resolution_summary")}</button>
      </div>
      <section class="notice daka-report-status" data-daka-report-status hidden></section>
      <section class="daka-report" data-daka-report-panel hidden></section>
    </div>
  `;

  const dateInput = dakaPane.querySelector("[data-daka-date]");
  const grid = dakaPane.querySelector("[data-daka-grid]");
  const reportStatus = dakaPane.querySelector("[data-daka-report-status]");
  const reportPane = dakaPane.querySelector("[data-daka-report-panel]");
  dateInput.addEventListener("change", () => {
    loadDakaState(dateInput.value).catch((error) => showError(error.message));
  });

  dakaPane.querySelectorAll("[data-daka-report-button]").forEach((button) => {
    button.addEventListener("click", () => {
      const reportKind = button.getAttribute("data-daka-report-button");
      if (!reportKind) return;
      loadDakaReport(reportKind, reportPane, reportStatus).catch((error) => showError(error.message));
    });
  });

  grid.replaceChildren();
  if (!payload.resolutions.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = t("no_daka_items");
    grid.append(empty);
    return;
  }

  payload.resolutions.forEach((resolution, index) => {
    const accent = pastelForName(resolution.name, index);
    const section = document.createElement("section");
    section.className = "daka-resolution";
    section.style.setProperty("--daka-accent", accent);

    const header = document.createElement("div");
    header.className = "daka-resolution-head";

    const heading = document.createElement("h2");
    heading.textContent = resolution.name;
    header.append(heading);

    const count = document.createElement("span");
    count.className = "daka-resolution-count";
    count.textContent = t("count_items", resolution.items.length);
    header.append(count);

    const items = document.createElement("div");
    items.className = "daka-items";

    for (const item of resolution.items) {
      const row = document.createElement("button");
      row.type = "button";
      row.className = `daka-item daka-item-row${item.checked ? " is-checked" : ""}`;
      row.setAttribute("aria-label", item.checked ? `${item.name}, ${t("today_checked")}` : `${item.name}, ${t("click_to_checkin")}`);
      if (item.checked) {
        row.setAttribute("aria-disabled", "true");
      }

      const label = document.createElement("div");
      label.className = "daka-item-label";

      const name = document.createElement("div");
      name.className = "daka-item-name";
      name.textContent = item.name;
      label.append(name);

      const meta = document.createElement("div");
      meta.className = "daka-item-meta";
      meta.textContent = t("total_checkins", item.checkin_count);
      label.append(meta);

      const badge = document.createElement("span");
      badge.className = "daka-item-badge";
      badge.textContent = item.checked ? t("today_checked") : t("click_to_checkin");

      row.addEventListener("click", () => {
        if (item.checked) return;
        handleDakaCheckin(resolution.name, item.name).catch((error) => showError(error.message));
      });

      row.append(label, badge);
      items.append(row);
    }

    section.append(header, items);
    grid.append(section);
  });
}

async function loadDakaReport(reportKind, reportPane, reportStatus, announce = true) {
  clearError();
  currentDakaReport = reportKind;
  const query = new URLSearchParams();
  if (currentDakaDate) query.set("date", currentDakaDate);
  query.set("report", reportKind);
  if (announce) {
    reportStatus.hidden = false;
    reportStatus.textContent = reportKind === "summary" ? t("report_task_summary_loading") : t("report_resolution_summary_loading");
  }
  const url = new URL("/api/tools/daka", window.location.origin);
  if (lang === "en") url.searchParams.set("lang", lang);
  for (const [key, value] of query.entries()) {
    url.searchParams.set(key, value);
  }
  const response = await fetch(url.toString(), { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || t("generate_report_error"));
  renderDakaReport(payload, reportPane);
  reportStatus.hidden = false;
  reportStatus.textContent = reportKind === "summary" ? t("report_task_summary_done") : t("report_resolution_summary_done");
  if (announce) {
    showStatus(reportStatus.textContent);
  }
}

function renderDakaReport(payload, reportPane) {
  reportPane.hidden = false;
  if (!payload.groups.length) {
    reportPane.innerHTML = `<div class="empty">${t("no_data")}</div>`;
    return;
  }

  const title = payload.report_kind === "summary" ? t("daka_task_summary") : t("daka_resolution_summary");
  const rows = payload.groups
    .map((group, index) => {
      const accent = cssColorForResolution(group.color, index);
      const bg = pastelForName(group.resolution || group.item || "", index);
      const label = payload.report_kind === "summary" ? `${group.resolution} / ${group.item}` : group.resolution;
      const subtitle = payload.report_kind === "summary" ? t("task_level") : t("resolution_level");
      return `
        <article class="daka-report-card" style="--report-accent:${accent}; --report-bg:${bg}">
          <div class="daka-report-head">
            <div>
              <div class="daka-report-label">${escapeHtml(label)}</div>
              <div class="daka-report-sub">${subtitle}</div>
            </div>
            <div class="daka-report-badges">
              <span class="daka-report-badge">${t("day_short")} ${escapeHtml(group.checked_days)}/${escapeHtml(group.day_total)}</span>
              <span class="daka-report-badge">${t("week_short")} ${escapeHtml(group.checked_weeks)}/${escapeHtml(group.week_total)}</span>
            </div>
          </div>
          <div class="daka-report-bars">
            <div class="daka-report-barline">
              <span>${t("annual_progress")}</span>
              <strong>${group.day_percent.toFixed(2)}%</strong>
            </div>
            <div class="daka-progress"><span style="width:${Math.min(group.day_percent, 100)}%"></span></div>
            <div class="daka-report-barline">
              <span>${t("weekly_progress")}</span>
              <strong>${group.week_percent.toFixed(2)}%</strong>
            </div>
            <div class="daka-progress daka-progress-week"><span style="width:${Math.min(group.week_percent, 100)}%"></span></div>
          </div>
        </article>
      `;
    })
    .join("");

  reportPane.innerHTML = `
    <div class="daka-report-title">${title} · ${payload.year}</div>
    <div class="daka-report-grid">${rows}</div>
  `;
}

async function handleDakaCheckin(resolutionName, itemName) {
  clearError();
  clearStatus();
  const url = new URL("/api/tools/daka/run", window.location.origin);
  if (lang === "en") url.searchParams.set("lang", lang);
  const response = await fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      date: currentDakaDate,
      resolution: resolutionName,
      item: itemName,
    }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || t("checkin_failed"));

  showStatus(result.stdout || result.message || t("checkin_done"));
  await loadDakaState(result.date || currentDakaDate, result.stdout || result.message || "");
}
