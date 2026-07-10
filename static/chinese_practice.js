import { fieldHtml } from "./tool_shared.js";

const toolId = window.__COMMAND_TOOL_ID__;
const form = document.querySelector("[data-tool-form]");
const fields = document.querySelector("[data-tool-fields]");
const output = document.querySelector("[data-tool-output]");
const errorBox = document.querySelector("[data-tool-error]");
const submit = document.querySelector("[data-tool-submit]");
const files = document.querySelector("[data-tool-files]");

function showError(message) {
  errorBox.hidden = false;
  errorBox.textContent = message;
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
}

function renderFields(args) {
  const htmlByName = new Map(args.map((arg) => [arg.name, fieldHtml(arg)]));
  for (const slot of fields.querySelectorAll("[data-tool-slot]")) {
    slot.innerHTML = htmlByName.get(slot.dataset.toolSlot) || "";
  }
}

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

async function loadTool() {
  const response = await fetch(`/api/tools/${encodeURIComponent(toolId)}`, { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "无法加载工具");

  document.querySelector("[data-tool-title]").textContent = payload.name;
  document.querySelector("[data-tool-description]").textContent = payload.description;
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
      payload[input.name] = input.value.trim();
    }

    const response = await fetch(`/api/tools/${encodeURIComponent(toolId)}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "工具运行失败");

    output.textContent = result.stdout || result.stderr || "（没有输出）";
    output.classList.toggle("failed", !result.ok);
    renderFiles(result.files || []);
  } catch (error) {
    showError(error.message);
  } finally {
    submit.disabled = false;
  }
});

loadTool().catch((error) => showError(error.message));
