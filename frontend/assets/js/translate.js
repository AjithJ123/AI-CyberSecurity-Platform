// Translator+ page controller.

import { ApiError, translateText } from "./api.js";

const $ = (id) => document.getElementById(id);
const MAX = 8000;

function el(tag, className, text) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text !== undefined) n.textContent = text;
  return n;
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
  box.append(spinner, el("span", "", "Translating…"));
  container.appendChild(box);
}

function renderError(container, message) {
  container.replaceChildren();
  const box = el("div", "pg-error-box", message || "Something went wrong. Please try again.");
  box.setAttribute("role", "alert");
  container.appendChild(box);
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

function renderResult(container, result) {
  container.replaceChildren();

  const card = el("article", "pg-verdict safe");
  card.setAttribute("aria-live", "polite");

  const head = el("div", "pg-verdict-head");
  const iconEl = el("span", "pg-verdict-icon");
  iconEl.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  iconEl.setAttribute("aria-hidden", "true");
  const titleWrap = el("div", "");
  titleWrap.appendChild(el("div", "pg-verdict-label", `${result.source_detected} → ${result.target}`));
  titleWrap.appendChild(el("div", "pg-verdict-title", "DONE"));
  head.append(iconEl, titleWrap);
  card.appendChild(head);

  const stats = el("p", "mt-3 text-sm", "");
  stats.style.color = "var(--pg-text-muted)";
  stats.textContent = `${result.word_count} word${result.word_count === 1 ? "" : "s"} · ${result.formality} register`;
  card.appendChild(stats);

  // Primary translation
  const block = el("div", "pg-rewrite-block");
  const blockHead = el("div", "pg-rewrite-head");
  blockHead.appendChild(el("div", "pg-section-title", "Translation"));
  const copyBtn = el("button", "pg-copy-btn", "Copy");
  copyBtn.type = "button";
  copyBtn.addEventListener("click", () => copyToClipboard(result.translated, copyBtn));
  blockHead.appendChild(copyBtn);
  block.appendChild(blockHead);
  block.appendChild(el("div", "pg-rewrite-text", result.translated));
  card.appendChild(block);

  // Alternative
  if (result.alternative) {
    const alt = el("div", "pg-rewrite-block");
    const altHead = el("div", "pg-rewrite-head");
    altHead.appendChild(el("div", "pg-section-title", "Alternative phrasing"));
    const altBtn = el("button", "pg-copy-btn", "Copy");
    altBtn.type = "button";
    altBtn.addEventListener("click", () => copyToClipboard(result.alternative, altBtn));
    altHead.appendChild(altBtn);
    alt.appendChild(altHead);
    alt.appendChild(el("div", "pg-rewrite-text", result.alternative));
    card.appendChild(alt);
  }

  // Translator notes
  if (Array.isArray(result.notes) && result.notes.length) {
    const box = el("div", "pg-actions");
    box.appendChild(el("div", "pg-actions-title", "Translator notes"));
    const ul = el("ul", "");
    for (const n of result.notes) ul.appendChild(el("li", "", n));
    box.appendChild(ul);
    card.appendChild(box);
  }

  // Meta
  const meta = el("footer", "pg-meta");
  meta.appendChild(el("span", "", `from: ${result.source_detected}`));
  meta.appendChild(el("span", "", `to: ${result.target}`));
  if (result.duration_ms) meta.appendChild(el("span", "", `dur: ${result.duration_ms}ms`));
  meta.appendChild(el("span", "", "engine: helix v1.0"));
  card.appendChild(meta);

  container.appendChild(card);
}

function init() {
  const form = $("tr-form");
  const input = $("tr-input");
  const source = $("tr-source");
  const target = $("tr-target");
  const counter = $("tr-counter");
  const submit = $("tr-submit");
  const errorEl = $("tr-error");
  const result = $("tr-result");
  const swapBtn = $("tr-swap");
  const chips = document.querySelectorAll(".pg-tone-chip");
  let formality = "default";

  const updateCounter = () => { counter.textContent = `${input.value.length} / ${MAX}`; };
  input.addEventListener("input", updateCounter);
  updateCounter();

  for (const chip of chips) {
    chip.addEventListener("click", () => {
      formality = chip.dataset.formality || "default";
      for (const c of chips) {
        const active = c === chip;
        c.classList.toggle("is-active", active);
        c.setAttribute("aria-checked", String(active));
      }
    });
  }

  swapBtn.addEventListener("click", () => {
    // Only swap if source isn't auto.
    if (source.value === "auto") return;
    const s = source.value;
    const t = target.value;
    source.value = t;
    target.value = s;
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) {
      showInlineError(errorEl, "Paste some text to translate.");
      return;
    }
    if (source.value !== "auto" && source.value === target.value) {
      showInlineError(errorEl, "Source and target languages are the same.");
      return;
    }
    showInlineError(errorEl, "");
    submit.disabled = true;
    setLoading(result);
    try {
      const data = await translateText({
        text,
        source: source.value,
        target: target.value,
        formality,
        preserveTone: true,
      });
      renderResult(result, data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "We couldn't reach the translator. Please try again.";
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
