import { fieldHtml } from "./tool_shared.js";

const toolId = window.__COMMAND_TOOL_ID__;
const t = (window.__HCC_I18N && window.__HCC_I18N.t) || ((key) => {
  if (key === "open") return "打开";
  if (key === "tool_load_error") return "无法加载工具";
  if (key === "tool_run_error") return "工具运行失败";
  if (key === "no_output") return "（没有输出）";
  if (key === "generate") return "生成";
  if (key === "practice_chars") return "练习汉字";
  if (key === "chars_too_long") return "汉字必须少于等于 40 个字符";
  if (key === "chars_only_chinese") return "只支持中文汉字";
  return key;
});
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
    link.textContent = `${t("open")} ${file.name}`;
    files.append(link);
  }
}

async function loadTool() {
  const url = new URL(`/api/tools/${encodeURIComponent(toolId)}`, window.location.origin);
  if (window.__HCC_LANG__ === "en") url.searchParams.set("lang", "en");
  const response = await fetch(url.toString(), { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || t("tool_load_error"));

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

    const runUrl = new URL(`/api/tools/${encodeURIComponent(toolId)}/run`, window.location.origin);
    if (window.__HCC_LANG__ === "en") runUrl.searchParams.set("lang", "en");
    const response = await fetch(runUrl.toString(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || t("tool_run_error"));

    output.textContent = result.stdout || result.stderr || t("no_output");
    output.classList.toggle("failed", !result.ok);
    renderFiles(result.files || []);
  } catch (error) {
    showError(error.message);
  } finally {
    submit.disabled = false;
  }
});

loadTool().catch((error) => showError(error.message));
