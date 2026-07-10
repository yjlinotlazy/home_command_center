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
let lastOutputText = "";
let currentDakaDate = "";
let currentDakaReport = "";

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
  const response = await fetch(`/api/tools/${encodeURIComponent(toolId)}`, { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "无法加载工具");

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

    const response = await fetch(`/api/tools/${encodeURIComponent(toolId)}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "工具运行失败");

    lastOutputText = result.stdout || result.stderr || "（没有输出）";
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
    link.textContent = `打开 ${file.name}`;
    files.append(link);
  }
}

async function loadDakaState(dateValue, statusMessage = "") {
  currentDakaDate = dateValue || currentDakaDate || "";
  if (!statusMessage) {
    clearStatus();
  }
  const query = currentDakaDate ? `?date=${encodeURIComponent(currentDakaDate)}` : "";
  const response = await fetch(`/api/tools/daka${query}`, { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "无法加载打卡数据");
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
        <span>日期</span>
        <input type="date" data-daka-date value="${escapeHtml(payload.date)}">
      </label>
    </div>
    <div class="daka-grid" data-daka-grid></div>
    <div class="daka-bottom">
      <div class="daka-actions">
        <button type="button" class="open daka-action" data-daka-report-button="summary">生成任务汇总</button>
        <button type="button" class="open daka-action" data-daka-report-button="resolution-summary">生成愿望汇总</button>
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
    empty.textContent = "还没有打卡项目。";
    grid.append(empty);
    return;
  }

  for (const resolution of payload.resolutions) {
    const section = document.createElement("section");
    section.className = "daka-resolution";

    const header = document.createElement("div");
    header.className = "daka-resolution-head";

    const heading = document.createElement("h2");
    heading.textContent = resolution.name;
    header.append(heading);

    const count = document.createElement("span");
    count.className = "daka-resolution-count";
    count.textContent = `${resolution.items.length} 项`;
    header.append(count);

    const items = document.createElement("div");
    items.className = "daka-items";

    for (const item of resolution.items) {
      const row = document.createElement("button");
      row.type = "button";
      row.className = `daka-item daka-item-row${item.checked ? " is-checked" : ""}`;
      row.setAttribute("aria-label", item.checked ? `${item.name}，今天已打卡` : `${item.name}，点击打卡`);
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
      meta.textContent = `累计 ${item.checkin_count} 次`;
      label.append(meta);

      const badge = document.createElement("span");
      badge.className = "daka-item-badge";
      badge.textContent = item.checked ? "已打卡" : "打卡";

      row.addEventListener("click", () => {
        if (item.checked) return;
        handleDakaCheckin(resolution.name, item.name).catch((error) => showError(error.message));
      });

      row.append(label, badge);
      items.append(row);
    }

    section.append(header, items);
    grid.append(section);
  }
}

async function loadDakaReport(reportKind, reportPane, reportStatus, announce = true) {
  clearError();
  currentDakaReport = reportKind;
  const query = new URLSearchParams();
  if (currentDakaDate) query.set("date", currentDakaDate);
  query.set("report", reportKind);
  if (announce) {
    reportStatus.hidden = false;
    reportStatus.textContent = reportKind === "summary" ? "正在生成任务汇总。" : "正在生成愿望汇总。";
  }
  const response = await fetch(`/api/tools/daka?${query.toString()}`, { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "无法生成报告");
  renderDakaReport(payload, reportPane);
  reportStatus.hidden = false;
  reportStatus.textContent = reportKind === "summary" ? "任务汇总已生成。" : "愿望汇总已生成。";
  if (announce) {
    showStatus(reportStatus.textContent);
  }
}

function renderDakaReport(payload, reportPane) {
  reportPane.hidden = false;
  if (!payload.groups.length) {
    reportPane.innerHTML = `<div class="empty">没有可显示的数据。</div>`;
    return;
  }

  const title = payload.report_kind === "summary" ? "任务汇总" : "愿望汇总";
  const rows = payload.groups
    .map((group, index) => {
      const accent = cssColorForResolution(group.color, index);
      const label = payload.report_kind === "summary" ? `${group.resolution} / ${group.item}` : group.resolution;
      const subtitle = payload.report_kind === "summary" ? "任务级别" : "愿望级别";
      return `
        <article class="daka-report-card" style="--report-accent:${accent}">
          <div class="daka-report-head">
            <div>
              <div class="daka-report-label">${escapeHtml(label)}</div>
              <div class="daka-report-sub">${subtitle}</div>
            </div>
            <div class="daka-report-badges">
              <span class="daka-report-badge">日 ${escapeHtml(group.checked_days)}/${escapeHtml(group.day_total)}</span>
              <span class="daka-report-badge">周 ${escapeHtml(group.checked_weeks)}/${escapeHtml(group.week_total)}</span>
            </div>
          </div>
          <div class="daka-report-bars">
            <div class="daka-report-barline">
              <span>年度进度</span>
              <strong>${group.day_percent.toFixed(2)}%</strong>
            </div>
            <div class="daka-progress"><span style="width:${Math.min(group.day_percent, 100)}%"></span></div>
            <div class="daka-report-barline">
              <span>周度进度</span>
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
  const response = await fetch(`/api/tools/daka/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      date: currentDakaDate,
      resolution: resolutionName,
      item: itemName,
    }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "打卡失败");

  showStatus(result.stdout || result.message || "打卡完成");
  await loadDakaState(result.date || currentDakaDate, result.stdout || result.message || "");
}
