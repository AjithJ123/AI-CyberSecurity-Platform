// Data Summarizer page controller.

import { ApiError, summarizeData } from "./api.js";

const $ = (id) => document.getElementById(id);
const MAX = 60000;

const SAMPLE = `product,month,region,units,revenue
Atlas,2026-01,NA,412,28840
Atlas,2026-01,EU,301,21070
Atlas,2026-02,NA,587,40999
Atlas,2026-02,EU,344,24008
Beacon,2026-01,NA,118,18880
Beacon,2026-01,EU,72,11520
Beacon,2026-02,NA,95,15200
Beacon,2026-02,EU,108,17280
Cipher,2026-01,NA,54,21600
Cipher,2026-01,EU,40,16000
Cipher,2026-02,NA,190,76000
Cipher,2026-02,EU,50,20000`;

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
  box.append(spinner, el("span", "", "Reading your data…"));
  container.appendChild(box);
}

function renderError(container, message) {
  container.replaceChildren();
  const box = el("div", "pg-error-box", message || "Something went wrong. Please try again.");
  box.setAttribute("role", "alert");
  container.appendChild(box);
}

function renderColumnsTable(cols) {
  const table = el("table", "pg-col-table");
  const thead = el("thead", "");
  const trh = el("tr", "");
  ["Column", "Type", "Filled", "Unique", "Min / Mean / Max"].forEach((h) => {
    trh.appendChild(el("th", "", h));
  });
  thead.appendChild(trh);
  table.appendChild(thead);

  const tbody = el("tbody", "");
  for (const c of cols) {
    const tr = el("tr", "");
    tr.appendChild(el("td", "pg-col-name", c.name));
    tr.appendChild(el("td", "pg-col-type", c.type));
    tr.appendChild(el("td", "pg-col-num", String(c.non_empty)));
    tr.appendChild(el("td", "pg-col-num", String(c.unique)));

    let stat = "—";
    if (c.type === "numeric" && c.mean != null) {
      stat = `${c.min} / ${c.mean} / ${c.max}`;
    } else if (c.type === "date" && c.min) {
      stat = `${c.min} → ${c.max}`;
    } else if (Array.isArray(c.sample_values) && c.sample_values.length) {
      stat = c.sample_values.slice(0, 3).join(", ");
    }
    const td = el("td", "pg-col-stat", stat);
    tr.appendChild(td);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

function renderResult(container, result) {
  container.replaceChildren();

  const card = el("article", "pg-verdict safe");
  card.setAttribute("aria-live", "polite");

  // Header
  const head = el("div", "pg-verdict-head");
  const iconEl = el("span", "pg-verdict-icon");
  iconEl.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>';
  iconEl.setAttribute("aria-hidden", "true");
  const titleWrap = el("div", "");
  titleWrap.appendChild(el("div", "pg-verdict-label", "Summary"));
  titleWrap.appendChild(el("div", "pg-verdict-title", "READY"));
  head.append(iconEl, titleWrap);
  card.appendChild(head);

  // Big stats row: rows × cols
  const stats = el("div", "pg-data-stats");
  const addStat = (label, value) => {
    const s = el("div", "pg-data-stat");
    s.appendChild(el("span", "pg-data-stat-value", value));
    s.appendChild(el("span", "pg-data-stat-label", label));
    stats.appendChild(s);
  };
  addStat("rows", String(result.row_count));
  addStat("columns", String(result.column_count));
  addStat("delimiter", result.delimiter);
  card.appendChild(stats);

  // One-line summary
  card.appendChild(el("div", "pg-recommendation", result.summary));

  if (result.truncated) {
    const warn = el("p", "pg-issue-fix", "⚠ Large table — only the first rows were summarized.");
    warn.style.marginTop = "0.5rem";
    card.appendChild(warn);
  }

  // Highlights
  if (Array.isArray(result.highlights) && result.highlights.length) {
    const sec = el("section", "");
    const head2 = el("div", "pg-section-head");
    head2.appendChild(el("h3", "pg-section-title", "Highlights"));
    head2.appendChild(el("span", "pg-chip", `${result.highlights.length}`));
    sec.appendChild(head2);
    const ul = el("ul", "pg-actions");
    ul.style.marginTop = "0.25rem";
    const innerUl = el("ul", "");
    for (const h of result.highlights) innerUl.appendChild(el("li", "", h));
    ul.appendChild(innerUl);
    sec.appendChild(ul);
    card.appendChild(sec);
  }

  // Outliers
  if (Array.isArray(result.outliers) && result.outliers.length) {
    const sec = el("section", "");
    const head3 = el("div", "pg-section-head");
    head3.appendChild(el("h3", "pg-section-title", "Outliers"));
    head3.appendChild(el("span", "pg-chip", `${result.outliers.length}`));
    sec.appendChild(head3);
    const list = el("ul", "pg-issue-list");
    for (const o of result.outliers) {
      const li = el("li", "pg-issue sev-readability");
      li.appendChild(el("p", "pg-issue-msg", o.description));
      if (o.detail) li.appendChild(el("p", "pg-issue-fix", o.detail));
      list.appendChild(li);
    }
    sec.appendChild(list);
    card.appendChild(sec);
  }

  // Column breakdown
  if (Array.isArray(result.columns) && result.columns.length) {
    const sec = el("section", "");
    const head4 = el("div", "pg-section-head");
    head4.appendChild(el("h3", "pg-section-title", "Columns"));
    head4.appendChild(el("span", "pg-chip", `${result.columns.length}`));
    sec.appendChild(head4);
    sec.appendChild(renderColumnsTable(result.columns));
    card.appendChild(sec);
  }

  // Meta
  const meta = el("footer", "pg-meta");
  meta.appendChild(el("span", "", `rows: ${result.row_count}`));
  meta.appendChild(el("span", "", `cols: ${result.column_count}`));
  if (result.duration_ms) meta.appendChild(el("span", "", `dur: ${result.duration_ms}ms`));
  meta.appendChild(el("span", "", "engine: helix v1.0"));
  card.appendChild(meta);

  container.appendChild(card);
}

function init() {
  const form = $("data-form");
  const input = $("data-input");
  const context = $("data-context");
  const counter = $("data-counter");
  const submit = $("data-submit");
  const errorEl = $("data-error");
  const result = $("data-result");
  const sampleBtn = $("data-sample-btn");
  const fileInput = $("data-file");

  const updateCounter = () => {
    const text = input.value;
    const rows = text ? text.split(/\r?\n/).filter(Boolean).length : 0;
    counter.textContent = `${text.length} / ${MAX} · ${rows} line${rows === 1 ? "" : "s"}`;
  };
  input.addEventListener("input", updateCounter);
  updateCounter();

  sampleBtn.addEventListener("click", () => {
    input.value = SAMPLE;
    context.value = "quarterly product sales by region";
    updateCounter();
  });

  fileInput.addEventListener("change", async () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) return;
    if (file.size > MAX) {
      showInlineError(errorEl, `File is larger than ${MAX} characters.`);
      return;
    }
    const text = await file.text();
    input.value = text.slice(0, MAX);
    updateCounter();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) {
      showInlineError(errorEl, "Paste a table or CSV to summarize.");
      return;
    }
    showInlineError(errorEl, "");
    submit.disabled = true;
    setLoading(result);
    try {
      const data = await summarizeData({ data: text, context: context.value.trim() });
      renderResult(result, data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "We couldn't reach the summarizer. Please try again.";
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
