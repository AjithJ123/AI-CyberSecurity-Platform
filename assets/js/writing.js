// Writing Assistant page — wires the form to the rewrite endpoint and
// renders the result with copy + before/after comparison.

import { ApiError, rewriteText } from "./api.js";

const $ = (id) => document.getElementById(id);
const MAX = 8000;

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function setLoading(container) {
  container.replaceChildren();
  const box = el("div", "pg-loading");
  box.setAttribute("role", "status");
  const spinner = el("span", "pg-loading-spinner");
  spinner.setAttribute("aria-hidden", "true");
  box.append(spinner, el("span", "", "Rewriting…"));
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
    () => {
      button.textContent = "Copy failed";
    },
  );
}

function renderResult(container, result) {
  container.replaceChildren();

  const card = el("article", "pg-verdict safe");
  card.setAttribute("aria-live", "polite");

  // Header
  const head = el("div", "pg-verdict-head");
  const iconEl = el("span", "pg-verdict-icon");
  iconEl.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4Z"/></svg>';
  iconEl.setAttribute("aria-hidden", "true");
  const titleWrap = el("div", "");
  titleWrap.appendChild(el("div", "pg-verdict-label", `Rewritten · ${result.tone}`));
  titleWrap.appendChild(el("div", "pg-verdict-title", "DONE"));
  head.append(iconEl, titleWrap);
  card.appendChild(head);

  // Word-count delta
  const inWords = Number(result.original_word_count) || 0;
  const outWords = Number(result.rewritten_word_count) || 0;
  const delta = outWords - inWords;
  const deltaText = delta === 0
    ? "same length"
    : `${delta > 0 ? "+" : ""}${delta} word${Math.abs(delta) === 1 ? "" : "s"}`;
  const stats = el("p", "mt-3 text-sm", "");
  stats.style.color = "var(--pg-text-muted)";
  stats.textContent = `${inWords} → ${outWords} words (${deltaText})`;
  card.appendChild(stats);

  // Rewritten text block with copy button
  const rewriteBlock = el("div", "pg-rewrite-block");
  const blockHead = el("div", "pg-rewrite-head");
  blockHead.appendChild(el("div", "pg-section-title", "Rewritten"));
  const copyBtn = el("button", "pg-copy-btn", "Copy");
  copyBtn.type = "button";
  copyBtn.addEventListener("click", () => copyToClipboard(result.rewritten, copyBtn));
  blockHead.appendChild(copyBtn);
  rewriteBlock.appendChild(blockHead);

  const pre = el("div", "pg-rewrite-text", result.rewritten);
  rewriteBlock.appendChild(pre);
  card.appendChild(rewriteBlock);

  // What changed
  if (Array.isArray(result.changes) && result.changes.length > 0) {
    const changesBox = el("div", "pg-actions");
    changesBox.appendChild(el("div", "pg-actions-title", "What changed"));
    const ul = el("ul", "");
    for (const c of result.changes) ul.appendChild(el("li", "", c));
    changesBox.appendChild(ul);
    card.appendChild(changesBox);
  }

  // Footer meta
  const meta = el("footer", "pg-meta");
  meta.appendChild(el("span", "", `tone: ${result.tone}`));
  if (result.duration_ms) meta.appendChild(el("span", "", `dur: ${result.duration_ms}ms`));
  meta.appendChild(el("span", "", "engine: helix v1.0"));
  card.appendChild(meta);

  container.appendChild(card);
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

function init() {
  const form = $("writer-form");
  const input = $("writer-input");
  const counter = $("writer-counter");
  const submit = $("writer-submit");
  const errorEl = $("writer-error");
  const result = $("writer-result");
  const chips = document.querySelectorAll(".pg-tone-chip");
  let tone = "natural";

  // Char counter.
  const updateCounter = () => {
    const len = input.value.length;
    counter.textContent = `${len} / ${MAX}`;
  };
  input.addEventListener("input", updateCounter);
  updateCounter();

  // Tone chip switching.
  for (const chip of chips) {
    chip.addEventListener("click", () => {
      tone = chip.dataset.tone || "natural";
      for (const c of chips) {
        const active = c === chip;
        c.classList.toggle("is-active", active);
        c.setAttribute("aria-checked", String(active));
      }
    });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) {
      showInlineError(errorEl, "Paste some text to rewrite.");
      return;
    }
    if (text.length > MAX) {
      showInlineError(errorEl, "Text is too long.");
      return;
    }
    showInlineError(errorEl, "");
    submit.disabled = true;
    setLoading(result);
    try {
      const data = await rewriteText({ text, tone });
      renderResult(result, data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "We couldn't reach the rewriter. Please try again.";
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
