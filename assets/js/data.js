// Data Summarizer page controller.
//
// Paste path: the textarea content is sent as-is (up to ~200k chars).
// Upload path: the whole file is read client-side, all rows are counted,
// a stratified sample (header + ~150 evenly-spaced rows) is sent with the
// real total row count. This lets the summarizer narrate a 119 MB file
// correctly without trying to shove the whole thing through the network.

import { ApiError, summarizeData } from "./api.js";

const $ = (id) => document.getElementById(id);
const MAX_PASTE_CHARS = 200_000;
const MAX_FILE_BYTES = 200 * 1024 * 1024; // 200 MB hard ceiling
const SAMPLE_ROWS = 150;                   // rows sent to the server

// Holds metadata when the user uploaded a file too big to paste.
let uploadSample = null; // { csv, totalRows, fileSizeBytes, delimiter, fileName }

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

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(2)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatNumber(n) {
  return n.toLocaleString();
}

// Detect delimiter from the first non-empty line.
function detectDelimiter(text) {
  const firstLine = text.split(/\r?\n/, 1)[0] || "";
  const counts = {
    ",": (firstLine.match(/,/g) || []).length,
    "\t": (firstLine.match(/\t/g) || []).length,
    ";": (firstLine.match(/;/g) || []).length,
    "|": (firstLine.match(/\|/g) || []).length,
  };
  let best = ",";
  let bestCount = counts[","];
  for (const [d, c] of Object.entries(counts)) {
    if (c > bestCount) { best = d; bestCount = c; }
  }
  return best;
}

/**
 * Stream-scan a File to count rows without loading it all at once.
 * Returns { totalRows, header, delimiter, sampleLines }.
 *
 * We read in chunks, split by newline, keep an even sample of lines across
 * the whole file. Only counts '\n' as a row separator which is the common
 * case. If the CSV contains quoted newlines the count may be slightly high,
 * but the summary still works from the sample.
 */
async function streamScan(file, onProgress) {
  const stream = file.stream();
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: false });

  let totalRows = 0;
  let header = "";
  let delimiter = ",";
  let carry = "";
  let bytesSoFar = 0;

  // Reservoir-ish stratified sampling — keep every Nth line after we pass
  // a first-pass burst. We update the step on the fly.
  const sampleLines = [];
  let rowIndex = 0;

  // To avoid gigantic in-memory sample when file is huge, we cap sampleLines
  // to SAMPLE_ROWS * 2 and thin it periodically.
  const MAX_BUFFER = SAMPLE_ROWS * 4;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    bytesSoFar += value.byteLength;
    if (onProgress) onProgress(bytesSoFar);

    carry += decoder.decode(value, { stream: true });
    const lines = carry.split("\n");
    carry = lines.pop() || ""; // last chunk may be partial

    for (const rawLine of lines) {
      const line = rawLine.replace(/\r$/, "");
      if (!header) {
        header = line;
        delimiter = detectDelimiter(header);
        continue;
      }
      if (!line) continue; // skip empty lines
      totalRows++;
      rowIndex++;

      // Keep the first SAMPLE_ROWS lines, then switch to stratified sampling
      // using a growing stride so the buffer never exceeds MAX_BUFFER.
      if (sampleLines.length < SAMPLE_ROWS) {
        sampleLines.push(line);
      } else {
        // Probabilistic replacement — roughly preserves uniform distribution.
        const j = Math.floor(Math.random() * rowIndex);
        if (j < SAMPLE_ROWS) {
          sampleLines[j] = line;
        }
      }
      if (sampleLines.length > MAX_BUFFER) {
        sampleLines.length = MAX_BUFFER;
      }
    }
  }

  // Tail — anything left in carry after stream ends.
  carry += decoder.decode();
  if (carry) {
    const line = carry.replace(/\r$/, "");
    if (!header) {
      header = line;
      delimiter = detectDelimiter(header);
    } else if (line) {
      totalRows++;
      if (sampleLines.length < SAMPLE_ROWS) sampleLines.push(line);
    }
  }

  // Trim sample to SAMPLE_ROWS.
  if (sampleLines.length > SAMPLE_ROWS) sampleLines.length = SAMPLE_ROWS;

  return { totalRows, header, delimiter, sampleLines };
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
    tr.appendChild(el("td", "pg-col-stat", stat));
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

function renderResult(container, result) {
  container.replaceChildren();

  const card = el("article", "pg-verdict safe");
  card.setAttribute("aria-live", "polite");

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

  const stats = el("div", "pg-data-stats");
  const addStat = (label, value) => {
    const s = el("div", "pg-data-stat");
    s.appendChild(el("span", "pg-data-stat-value", value));
    s.appendChild(el("span", "pg-data-stat-label", label));
    stats.appendChild(s);
  };
  addStat("rows", formatNumber(result.row_count));
  addStat("columns", String(result.column_count));
  addStat("delimiter", result.delimiter);
  card.appendChild(stats);

  card.appendChild(el("div", "pg-recommendation", result.summary));

  if (
    result.sampled_row_count &&
    result.sampled_row_count < result.row_count
  ) {
    const note = el(
      "p",
      "pg-issue-fix",
      `ⓘ Narrative based on a representative ${formatNumber(result.sampled_row_count)}-row sample of your ${formatNumber(result.row_count)}-row file.`,
    );
    note.style.marginTop = "0.5rem";
    card.appendChild(note);
  }

  if (Array.isArray(result.highlights) && result.highlights.length) {
    const sec = el("section", "");
    const hh = el("div", "pg-section-head");
    hh.appendChild(el("h3", "pg-section-title", "Highlights"));
    hh.appendChild(el("span", "pg-chip", `${result.highlights.length}`));
    sec.appendChild(hh);
    const box = el("div", "pg-actions");
    box.style.marginTop = "0.25rem";
    const ul = el("ul", "");
    for (const h of result.highlights) ul.appendChild(el("li", "", h));
    box.appendChild(ul);
    sec.appendChild(box);
    card.appendChild(sec);
  }

  if (Array.isArray(result.outliers) && result.outliers.length) {
    const sec = el("section", "");
    const hh = el("div", "pg-section-head");
    hh.appendChild(el("h3", "pg-section-title", "Outliers"));
    hh.appendChild(el("span", "pg-chip", `${result.outliers.length}`));
    sec.appendChild(hh);
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

  if (Array.isArray(result.columns) && result.columns.length) {
    const sec = el("section", "");
    const hh = el("div", "pg-section-head");
    hh.appendChild(el("h3", "pg-section-title", "Columns"));
    hh.appendChild(el("span", "pg-chip", `${result.columns.length}`));
    sec.appendChild(hh);
    sec.appendChild(renderColumnsTable(result.columns));
    card.appendChild(sec);
  }

  const meta = el("footer", "pg-meta");
  meta.appendChild(el("span", "", `rows: ${formatNumber(result.row_count)}`));
  if (result.sampled_row_count) {
    meta.appendChild(el("span", "", `sample: ${formatNumber(result.sampled_row_count)}`));
  }
  meta.appendChild(el("span", "", `cols: ${result.column_count}`));
  if (result.duration_ms) meta.appendChild(el("span", "", `dur: ${result.duration_ms}ms`));
  meta.appendChild(el("span", "", "engine: helix v1.0"));
  card.appendChild(meta);

  container.appendChild(card);
}

function renderFileStatus(statusEl, info, progressText) {
  statusEl.replaceChildren();
  statusEl.hidden = false;

  const wrap = el("div", "pg-file-status");

  const titleRow = el("div", "pg-file-status-head");
  titleRow.appendChild(el("span", "pg-file-status-dot"));
  titleRow.appendChild(el("span", "pg-file-status-name", info.fileName));
  titleRow.appendChild(el("span", "pg-file-status-size", formatBytes(info.fileSizeBytes)));
  wrap.appendChild(titleRow);

  if (progressText) {
    wrap.appendChild(el("p", "pg-file-status-msg", progressText));
  } else {
    wrap.appendChild(
      el(
        "p",
        "pg-file-status-msg",
        `${formatNumber(info.totalRows)} rows · delimiter "${info.delimiter === "\t" ? "tab" : info.delimiter}" · sampling ${info.sampleLines.length} rows for analysis.`,
      ),
    );
  }

  statusEl.appendChild(wrap);
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

  // Inject a status element above the textarea for file uploads.
  let statusEl = document.getElementById("data-file-status");
  if (!statusEl) {
    statusEl = el("div", "");
    statusEl.id = "data-file-status";
    statusEl.hidden = true;
    // Place above the textarea label.
    const counterLabel = counter ? counter.closest("label") : null;
    if (counterLabel) {
      counterLabel.parentNode.insertBefore(statusEl, counterLabel);
    }
  }

  const updateCounter = () => {
    const text = input.value;
    const rows = text ? text.split(/\r?\n/).filter(Boolean).length : 0;
    counter.textContent = `${formatNumber(text.length)} / ${formatNumber(MAX_PASTE_CHARS)} · ${formatNumber(rows)} line${rows === 1 ? "" : "s"}`;
  };
  input.addEventListener("input", () => {
    // Any manual edit clears the upload sample — we'll send the textarea text.
    uploadSample = null;
    statusEl.hidden = true;
    updateCounter();
  });
  updateCounter();

  sampleBtn.addEventListener("click", () => {
    uploadSample = null;
    statusEl.hidden = true;
    input.value = SAMPLE;
    context.value = "quarterly product sales by region";
    updateCounter();
  });

  fileInput.addEventListener("change", async () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      showInlineError(errorEl, `File is ${formatBytes(file.size)} — max ${formatBytes(MAX_FILE_BYTES)}.`);
      return;
    }
    showInlineError(errorEl, "");

    const info = { fileName: file.name, fileSizeBytes: file.size };
    renderFileStatus(statusEl, { ...info, totalRows: 0, delimiter: ",", sampleLines: [] }, `Reading ${formatBytes(file.size)}…`);

    let lastUpdate = 0;
    try {
      const scan = await streamScan(file, (bytes) => {
        const now = performance.now();
        if (now - lastUpdate > 200) {
          lastUpdate = now;
          const pct = Math.min(100, Math.round((bytes / file.size) * 100));
          renderFileStatus(statusEl, { ...info, totalRows: 0, delimiter: ",", sampleLines: [] }, `Scanning… ${pct}%`);
        }
      });
      uploadSample = {
        csv: [scan.header, ...scan.sampleLines].join("\n"),
        totalRows: scan.totalRows,
        fileSizeBytes: file.size,
        delimiter: scan.delimiter,
        fileName: file.name,
        sampleLines: scan.sampleLines,
      };
      renderFileStatus(statusEl, { ...info, totalRows: scan.totalRows, delimiter: scan.delimiter, sampleLines: scan.sampleLines });

      // Put a friendly preview in the textarea (header + first 10 sample lines).
      const preview = [
        scan.header,
        ...scan.sampleLines.slice(0, 10),
        `# ... sending a ${scan.sampleLines.length}-row sample from ${formatNumber(scan.totalRows)} total rows to the AI`,
      ].join("\n");
      input.value = preview;
      updateCounter();
    } catch (err) {
      showInlineError(errorEl, "Could not read the file.");
      statusEl.hidden = true;
      uploadSample = null;
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    let dataToSend = input.value.trim();
    let totalRowsHint = null;
    let fileSizeBytes = null;

    // If the user uploaded a big file, send the stratified sample + hint instead
    // of whatever preview happens to be in the textarea.
    if (uploadSample) {
      dataToSend = uploadSample.csv;
      totalRowsHint = uploadSample.totalRows;
      fileSizeBytes = uploadSample.fileSizeBytes;
    }

    if (!dataToSend) {
      showInlineError(errorEl, "Paste a table or upload a file to summarize.");
      return;
    }
    showInlineError(errorEl, "");
    submit.disabled = true;
    setLoading(result);
    try {
      const data = await summarizeData({
        data: dataToSend,
        context: context.value.trim(),
        totalRowsHint,
        fileSizeBytes,
      });
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
