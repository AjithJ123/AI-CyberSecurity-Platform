// Code Reviewer page controller.

import { ApiError, reviewCode } from "./api.js";

const $ = (id) => document.getElementById(id);
const MAX = 12000;

const SEVERITY_LABEL = {
  bug: "Bug",
  security: "Security",
  readability: "Readability",
  style: "Style",
};
const SEVERITY_ORDER = ["bug", "security", "readability", "style"];

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
  box.append(spinner, el("span", "", "Reviewing code…"));
  container.appendChild(box);
}

function renderError(container, message) {
  container.replaceChildren();
  const box = el("div", "pg-error-box", message || "Something went wrong. Please try again.");
  box.setAttribute("role", "alert");
  container.appendChild(box);
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

function qualityVerdict(quality) {
  if (quality >= 8) return { label: "SOLID", cls: "safe" };
  if (quality >= 5) return { label: "OKAY", cls: "suspicious" };
  return { label: "NEEDS WORK", cls: "dangerous" };
}

function renderResult(container, result) {
  container.replaceChildren();
  const verdict = qualityVerdict(result.overall_quality);

  const card = el("article", `pg-verdict ${verdict.cls}`);
  card.setAttribute("aria-live", "polite");

  // Header
  const head = el("div", "pg-verdict-head");
  const iconEl = el("span", "pg-verdict-icon");
  iconEl.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 16 4-4-4-4"/><path d="m6 8-4 4 4 4"/><path d="m14.5 4-5 16"/></svg>';
  iconEl.setAttribute("aria-hidden", "true");
  const titleWrap = el("div", "");
  titleWrap.appendChild(el("div", "pg-verdict-label", `Review · ${result.language_detected}`));
  titleWrap.appendChild(el("div", "pg-verdict-title", verdict.label));
  head.append(iconEl, titleWrap);
  card.appendChild(head);

  // Quality score bar
  const scoreRow = el("div", "pg-score-row");
  scoreRow.appendChild(el("span", "", "Quality"));
  scoreRow.appendChild(el("span", "pg-score-value", `${result.overall_quality} / 10`));
  card.appendChild(scoreRow);
  const track = el("div", "pg-score-track");
  const fill = el("div", "pg-score-fill");
  fill.style.width = `${(result.overall_quality / 10) * 100}%`;
  track.appendChild(fill);
  card.appendChild(track);

  // Summary
  card.appendChild(el("div", "pg-recommendation", result.summary));

  // Issues grouped by severity
  const issues = Array.isArray(result.issues) ? result.issues : [];
  if (issues.length > 0) {
    const section = el("section", "");
    const header = el("div", "pg-section-head");
    header.appendChild(el("h3", "pg-section-title", "Issues"));
    header.appendChild(el("span", "pg-chip", `${issues.length} found`));
    section.appendChild(header);

    const list = el("ul", "pg-issue-list");
    const sorted = [...issues].sort(
      (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity),
    );
    for (const issue of sorted) {
      const li = el("li", `pg-issue sev-${issue.severity}`);
      const top = el("div", "pg-issue-top");
      const sev = el("span", `pg-sev-pill sev-${issue.severity}`, SEVERITY_LABEL[issue.severity] || issue.severity);
      top.appendChild(sev);
      if (issue.line != null) {
        top.appendChild(el("span", "pg-issue-line", `line ${issue.line}`));
      }
      li.appendChild(top);
      li.appendChild(el("p", "pg-issue-msg", issue.message));
      if (issue.suggestion) {
        li.appendChild(el("p", "pg-issue-fix", `→ ${issue.suggestion}`));
      }
      list.appendChild(li);
    }
    section.appendChild(list);
    card.appendChild(section);
  } else {
    const box = el("div", "pg-actions");
    box.appendChild(el("div", "pg-actions-title", "Issues"));
    const p = el("p", "", "No issues detected. Nicely done.");
    p.style.marginTop = "0.35rem";
    p.style.fontSize = "0.9rem";
    box.appendChild(p);
    card.appendChild(box);
  }

  // Positives
  const positives = Array.isArray(result.positives) ? result.positives : [];
  if (positives.length > 0) {
    const box = el("div", "pg-actions");
    box.appendChild(el("div", "pg-actions-title", "Strengths"));
    const ul = el("ul", "");
    for (const p of positives) ul.appendChild(el("li", "", p));
    box.appendChild(ul);
    card.appendChild(box);
  }

  // Meta
  const meta = el("footer", "pg-meta");
  meta.appendChild(el("span", "", `lines: ${result.line_count}`));
  meta.appendChild(el("span", "", `lang: ${result.language_detected}`));
  if (result.duration_ms) meta.appendChild(el("span", "", `dur: ${result.duration_ms}ms`));
  meta.appendChild(el("span", "", "engine: helix v1.0"));
  card.appendChild(meta);

  container.appendChild(card);
}

function init() {
  const form = $("code-form");
  const input = $("code-input");
  const lang = $("code-lang");
  const context = $("code-context");
  const counter = $("code-counter");
  const submit = $("code-submit");
  const errorEl = $("code-error");
  const result = $("code-result");

  const updateCounter = () => {
    counter.textContent = `${input.value.length} / ${MAX}`;
  };
  input.addEventListener("input", updateCounter);
  updateCounter();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const code = input.value;
    if (!code.trim()) {
      showInlineError(errorEl, "Paste some code to review.");
      return;
    }
    if (code.length > MAX) {
      showInlineError(errorEl, "Snippet is too long.");
      return;
    }
    showInlineError(errorEl, "");
    submit.disabled = true;
    setLoading(result);
    try {
      const data = await reviewCode({
        code,
        language: lang.value || "auto",
        context: context.value.trim(),
      });
      renderResult(result, data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "We couldn't reach the reviewer. Please try again.";
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
