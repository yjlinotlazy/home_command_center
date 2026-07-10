const toolId = window.__COMMAND_TOOL_ID__;
const form = document.querySelector("[data-tool-form]");
const fields = document.querySelector("[data-tool-fields]");
const output = document.querySelector("[data-tool-output]");
const errorBox = document.querySelector("[data-tool-error]");
const submit = document.querySelector("[data-tool-submit]");
const files = document.querySelector("[data-tool-files]");
const mobileOutputQuery = window.matchMedia("(max-width: 720px)");
let lastOutputText = "";

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

async function loadTool() {
  const response = await fetch(`/api/tools/${encodeURIComponent(toolId)}`, { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "无法加载工具");

  document.querySelector("[data-tool-title]").textContent = payload.name;
  document.querySelector("[data-tool-description]").textContent = payload.description;
  fields.innerHTML = payload.args.map(fieldHtml).join("");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  output.textContent = "";
  files.replaceChildren();
  submit.disabled = true;

  try {
    const payload = {};
    for (const input of fields.querySelectorAll("input, textarea, select")) {
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
