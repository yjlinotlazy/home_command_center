const text = window.__QUICK_PIC_TEXT__ || {};
const form = document.querySelector("[data-quick-pic-form]");
const candidatePanel = document.querySelector("[data-quick-pic-candidates]");
const outputNameInput = document.querySelector("[data-quick-pic-output-name]");
const backgroundSelect = document.querySelector("[data-quick-pic-background]");
const thresholdInput = document.querySelector("[data-quick-pic-threshold]");
const thresholdValue = document.querySelector("[data-quick-pic-threshold-value]");
const scaleInput = document.querySelector("[data-quick-pic-scale]");
const outputSelect = document.querySelector("[data-quick-pic-output]");
const originalImage = document.querySelector("[data-quick-pic-original]");
const processedImage = document.querySelector("[data-quick-pic-processed]");
const loading = document.querySelector("[data-quick-pic-loading]");
const saveButton = document.querySelector("[data-quick-pic-save]");
const errorBox = document.querySelector("[data-quick-pic-error]");
const statusBox = document.querySelector("[data-quick-pic-status]");

let candidates = [];
let selectedCandidateId = "";
let previewObjectUrl = "";
let previewTimer = 0;
let previewController = null;
let previewSequence = 0;

function selectedCandidate() {
  return candidates.find((candidate) => candidate.id === selectedCandidateId);
}

function requestPayload() {
  return {
    candidate_id: selectedCandidateId,
    background: backgroundSelect.value,
    threshold: Number(thresholdInput.value),
    scale_percent: Number(scaleInput.value),
  };
}

function showError(message) {
  errorBox.hidden = false;
  errorBox.textContent = message;
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
}

function clearStatus() {
  statusBox.hidden = true;
  statusBox.replaceChildren();
}

async function errorMessage(response, fallback) {
  try {
    const payload = await response.clone().json();
    return payload.error || fallback;
  } catch (_error) {
    return fallback;
  }
}

function renderOptions(select, items, labelFor) {
  select.replaceChildren();
  for (const item of items) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = labelFor(item);
    select.append(option);
  }
}

function renderCandidates() {
  candidatePanel.replaceChildren();
  for (const candidate of candidates) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quick-pic-candidate";
    button.dataset.candidateId = candidate.id;
    button.setAttribute("aria-pressed", String(candidate.id === selectedCandidateId));

    const image = document.createElement("img");
    image.src = candidate.source_url;
    image.alt = "";
    image.loading = "lazy";

    const name = document.createElement("span");
    name.textContent = candidate.name;
    name.title = candidate.name;

    button.append(image, name);
    button.addEventListener("click", () => selectCandidate(candidate.id));
    candidatePanel.append(button);
  }
}

function selectCandidate(candidateId) {
  if (candidateId === selectedCandidateId) return;
  selectedCandidateId = candidateId;
  for (const button of candidatePanel.querySelectorAll("[data-candidate-id]")) {
    const selected = button.dataset.candidateId === selectedCandidateId;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  }
  clearStatus();
  renderOriginal();
  schedulePreview();
}

function renderOriginal() {
  const candidate = selectedCandidate();
  originalImage.hidden = !candidate;
  originalImage.src = candidate ? candidate.source_url : "";
  originalImage.alt = candidate ? candidate.name : "";
}

function fitCanvasToImage(image) {
  if (!image.naturalWidth || !image.naturalHeight) return;
  const canvas = image.closest(".quick-pic-canvas");
  canvas.style.aspectRatio = `${image.naturalWidth} / ${image.naturalHeight}`;
  canvas.classList.add("has-image");
}

function schedulePreview() {
  window.clearTimeout(previewTimer);
  previewTimer = window.setTimeout(loadPreview, 250);
}

async function loadPreview() {
  if (!selectedCandidateId) return;

  const sequence = ++previewSequence;
  if (previewController) previewController.abort();
  previewController = new AbortController();
  loading.hidden = false;
  processedImage.hidden = true;
  clearError();

  try {
    const response = await fetch("/api/tools/quick_pic/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestPayload()),
      signal: previewController.signal,
    });
    if (!response.ok) {
      throw new Error(await errorMessage(response, text.preview_error));
    }
    const blob = await response.blob();
    if (sequence !== previewSequence) return;
    if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
    previewObjectUrl = URL.createObjectURL(blob);
    processedImage.src = previewObjectUrl;
    processedImage.hidden = false;
  } catch (error) {
    if (error.name !== "AbortError") {
      showError(error.message || text.preview_error);
    }
  } finally {
    if (sequence === previewSequence) loading.hidden = true;
  }
}

async function loadInitialState() {
  const url = new URL("/api/tools/quick_pic/candidates", window.location.origin);
  if (window.__HCC_LANG__ === "en") url.searchParams.set("lang", "en");
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(await errorMessage(response, text.load_error));
  const payload = await response.json();

  candidates = payload.candidates || [];
  selectedCandidateId = candidates[0]?.id || "";
  renderCandidates();
  candidatePanel.querySelector("[data-candidate-id]")?.classList.add("is-selected");
  renderOptions(outputSelect, payload.output_dirs || [], (directory) => directory.label);

  backgroundSelect.value = payload.defaults.background;
  thresholdInput.value = String(payload.defaults.threshold);
  thresholdValue.value = String(payload.defaults.threshold);
  scaleInput.value = String(payload.defaults.scale_percent);

  if (!candidates.length) {
    for (const control of form.querySelectorAll("input, select, button")) {
      control.disabled = true;
    }
    throw new Error(text.no_images);
  }
  if (!outputSelect.options.length) {
    throw new Error(text.load_error);
  }

  renderOriginal();
  await loadPreview();
}

backgroundSelect.addEventListener("change", () => {
  clearStatus();
  schedulePreview();
});

thresholdInput.addEventListener("input", () => {
  thresholdValue.value = thresholdInput.value;
  clearStatus();
  schedulePreview();
});

originalImage.addEventListener("load", () => fitCanvasToImage(originalImage));
processedImage.addEventListener("load", () => fitCanvasToImage(processedImage));

scaleInput.addEventListener("input", () => {
  clearStatus();
  if (scaleInput.checkValidity()) schedulePreview();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  clearStatus();
  saveButton.disabled = true;
  saveButton.textContent = text.saving;

  try {
    const payload = {
      ...requestPayload(),
      output_dir_id: outputSelect.value,
      output_name: outputNameInput.value,
    };
    const response = await fetch("/api/tools/quick_pic/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await errorMessage(response, text.preview_error));
    const result = await response.json();

    const prefix = document.createTextNode(`${text.saved}: ${result.output_label} / `);
    const link = document.createElement("a");
    link.href = result.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = result.name;
    statusBox.replaceChildren(prefix, link);
    statusBox.hidden = false;
    statusBox.classList.add("tool-status");
  } catch (error) {
    showError(error.message || text.preview_error);
  } finally {
    saveButton.disabled = false;
    saveButton.textContent = text.save;
  }
});

window.addEventListener("beforeunload", () => {
  if (previewController) previewController.abort();
  if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
});

loadInitialState().catch((error) => showError(error.message || text.load_error));
