// Image Analyzer page controller.

import { ApiError, analyzeImage } from "./api.js";

const $ = (id) => document.getElementById(id);
const MAX_BYTES = 8 * 1024 * 1024; // 8 MB raw file
const ACCEPTED = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"];

let currentFile = null;
let currentDataUrl = "";

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function showInlineError(errorEl, message) {
  if (!errorEl) return;
  if (message) {
    errorEl.textContent = message;
    errorEl.hidden = false;
  } else {
    errorEl.textContent = "";
    errorEl.hidden = true;
  }
}

function setLoading(container) {
  container.replaceChildren();
  const box = el("div", "pg-loading");
  box.setAttribute("role", "status");
  const spinner = el("span", "pg-loading-spinner");
  spinner.setAttribute("aria-hidden", "true");
  box.append(spinner, el("span", "", "Analyzing image…"));
  container.appendChild(box);
}

function renderError(container, message) {
  container.replaceChildren();
  const box = el("div", "pg-error-box", message || "Something went wrong. Please try again.");
  box.setAttribute("role", "alert");
  container.appendChild(box);
}

function aiVerdict(score) {
  if (score >= 70) return { label: "LIKELY AI", cls: "dangerous" };
  if (score >= 30) return { label: "UNCERTAIN", cls: "suspicious" };
  return { label: "LIKELY REAL", cls: "safe" };
}

function copyToClipboard(text, button) {
  navigator.clipboard.writeText(text).then(
    () => {
      const original = button.textContent;
      button.textContent = "Copied ✓";
      setTimeout(() => { button.textContent = original; }, 1800);
    },
    () => { button.textContent = "Copy failed"; },
  );
}

function renderResult(container, result, previewSrc) {
  container.replaceChildren();
  const v = aiVerdict(result.ai_generated_score);

  const card = el("article", `pg-verdict ${v.cls}`);
  card.setAttribute("aria-live", "polite");

  // Header
  const head = el("div", "pg-verdict-head");
  const iconEl = el("span", "pg-verdict-icon");
  iconEl.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>';
  iconEl.setAttribute("aria-hidden", "true");
  const titleWrap = el("div", "");
  titleWrap.appendChild(el("div", "pg-verdict-label", "Image analysis"));
  titleWrap.appendChild(el("div", "pg-verdict-title", v.label));
  head.append(iconEl, titleWrap);
  card.appendChild(head);

  // Two-column layout: thumbnail + detail
  const body = el("div", "pg-image-body");

  if (previewSrc) {
    const left = el("div", "pg-image-thumb");
    const img = document.createElement("img");
    img.src = previewSrc;
    img.alt = "Submitted image";
    left.appendChild(img);
    body.appendChild(left);
  }

  const right = el("div", "pg-image-detail");

  // AI score bar
  const scoreRow = el("div", "pg-score-row");
  scoreRow.appendChild(el("span", "", "AI-generated likelihood"));
  scoreRow.appendChild(el("span", "pg-score-value", `${result.ai_generated_score} / 100`));
  right.appendChild(scoreRow);
  const track = el("div", "pg-score-track");
  const fill = el("div", "pg-score-fill");
  fill.style.width = `${Math.max(0, Math.min(100, result.ai_generated_score))}%`;
  track.appendChild(fill);
  right.appendChild(track);

  // Description
  right.appendChild(el("div", "pg-recommendation", result.description));

  // Subjects chips
  if (Array.isArray(result.subjects) && result.subjects.length > 0) {
    const subWrap = el("div", "pg-subjects");
    for (const s of result.subjects) {
      subWrap.appendChild(el("span", "pg-chip", s));
    }
    right.appendChild(subWrap);
  }

  body.appendChild(right);
  card.appendChild(body);

  // AI-generated reasons
  if (Array.isArray(result.ai_generated_reasons) && result.ai_generated_reasons.length > 0) {
    const section = el("section", "");
    const head2 = el("div", "pg-section-head");
    head2.appendChild(el("h3", "pg-section-title", "Why this score"));
    head2.appendChild(el("span", "pg-chip", `${result.ai_generated_reasons.length} signals`));
    section.appendChild(head2);
    const ul = el("ul", "pg-issue-list");
    for (const r of result.ai_generated_reasons) {
      const li = el("li", "pg-issue sev-readability");
      li.appendChild(el("p", "pg-issue-msg", r));
      ul.appendChild(li);
    }
    section.appendChild(ul);
    card.appendChild(section);
  }

  // OCR
  if (result.has_text && result.ocr_text) {
    const block = el("div", "pg-rewrite-block");
    const head3 = el("div", "pg-rewrite-head");
    head3.appendChild(el("div", "pg-section-title", "Extracted text (OCR)"));
    const copyBtn = el("button", "pg-copy-btn", "Copy");
    copyBtn.type = "button";
    copyBtn.addEventListener("click", () => copyToClipboard(result.ocr_text, copyBtn));
    head3.appendChild(copyBtn);
    block.appendChild(head3);
    block.appendChild(el("div", "pg-rewrite-text", result.ocr_text));
    card.appendChild(block);
  }

  // Content warnings
  if (Array.isArray(result.content_warnings) && result.content_warnings.length > 0) {
    const box = el("div", "pg-actions");
    box.appendChild(el("div", "pg-actions-title", "Content warnings"));
    const ul = el("ul", "");
    for (const w of result.content_warnings) ul.appendChild(el("li", "", w));
    box.appendChild(ul);
    card.appendChild(box);
  }

  // Footer meta
  const meta = el("footer", "pg-meta");
  meta.appendChild(el("span", "", `model: ${result.model}`));
  if (result.duration_ms) meta.appendChild(el("span", "", `dur: ${result.duration_ms}ms`));
  meta.appendChild(el("span", "", "engine: helix v1.0"));
  card.appendChild(meta);

  container.appendChild(card);
}

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Could not read the file"));
    reader.readAsDataURL(file);
  });
}

async function setFile(file, errorEl, drop, dropEmpty, dropPreview, previewImg, previewName, previewSize, submit) {
  showInlineError(errorEl, "");
  if (!file) return;
  if (!ACCEPTED.includes(file.type)) {
    showInlineError(errorEl, "Pick a PNG, JPG, WebP, or GIF.");
    return;
  }
  if (file.size > MAX_BYTES) {
    showInlineError(errorEl, `File is ${formatBytes(file.size)} — max 8 MB.`);
    return;
  }
  try {
    const dataUrl = await readFileAsDataURL(file);
    currentFile = file;
    currentDataUrl = dataUrl;
    previewImg.src = dataUrl;
    previewName.textContent = file.name;
    previewSize.textContent = formatBytes(file.size);
    dropEmpty.hidden = true;
    dropPreview.hidden = false;
    drop.classList.add("has-file");
    submit.disabled = false;
  } catch (e) {
    showInlineError(errorEl, "Could not read that file.");
  }
}

function clearFile(drop, dropEmpty, dropPreview, fileInput, submit) {
  currentFile = null;
  currentDataUrl = "";
  fileInput.value = "";
  dropEmpty.hidden = false;
  dropPreview.hidden = true;
  drop.classList.remove("has-file");
  submit.disabled = true;
}

function init() {
  const form = $("image-form");
  const drop = $("image-drop");
  const dropEmpty = $("image-drop-empty");
  const dropPreview = $("image-drop-preview");
  const fileInput = $("image-file");
  const previewImg = $("image-preview-img");
  const previewName = $("image-preview-name");
  const previewSize = $("image-preview-size");
  const clearBtn = $("image-clear-btn");
  const submit = $("image-submit");
  const errorEl = $("image-error");
  const result = $("image-result");

  // Click to open picker.
  drop.addEventListener("click", (e) => {
    if (e.target === clearBtn) return;
    fileInput.click();
  });
  drop.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });

  // File input change.
  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    setFile(file, errorEl, drop, dropEmpty, dropPreview, previewImg, previewName, previewSize, submit);
  });

  // Drag-and-drop.
  ["dragenter", "dragover"].forEach((ev) => {
    drop.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      drop.classList.add("is-dragging");
    });
  });
  ["dragleave", "drop"].forEach((ev) => {
    drop.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      drop.classList.remove("is-dragging");
    });
  });
  drop.addEventListener("drop", (e) => {
    const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    setFile(file, errorEl, drop, dropEmpty, dropPreview, previewImg, previewName, previewSize, submit);
  });

  clearBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    clearFile(drop, dropEmpty, dropPreview, fileInput, submit);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!currentDataUrl || !currentFile) {
      showInlineError(errorEl, "Pick an image first.");
      return;
    }
    showInlineError(errorEl, "");
    submit.disabled = true;
    setLoading(result);
    try {
      const data = await analyzeImage({
        imageDataUrl: currentDataUrl,
        filename: currentFile.name,
      });
      renderResult(result, data, currentDataUrl);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "We couldn't reach the analyzer. Please try again.";
      renderError(result, msg);
    } finally {
      submit.disabled = false;
    }
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
