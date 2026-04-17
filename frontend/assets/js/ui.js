// DOM helpers and result rendering. Always escape backend-provided strings.

const VERDICT_META = {
  safe: {
    label: "SECURE",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>`,
  },
  suspicious: {
    label: "SUSPICIOUS",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`,
  },
  dangerous: {
    label: "DANGEROUS",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m9 9 6 6"/><path d="m15 9-6 6"/></svg>`,
  },
};

const SOURCE_META = {
  heuristics: { label: "Heuristics", desc: "Offline URL pattern analysis" },
  whois: { label: "WHOIS", desc: "Domain age, registrar, expiry" },
  safe_browsing: { label: "Safe Browsing", desc: "Google's known-threat database" },
  virustotal: { label: "VirusTotal", desc: "70+ antivirus engines" },
  phishtank: { label: "PhishTank", desc: "Community phishing reports" },
  ai: { label: "AI analyst", desc: "Content-based LLM review" },
  email_address: {
    label: "Address analysis",
    desc: "Format, disposable, typosquat, TLD",
  },
  shortener: {
    label: "Link shortener",
    desc: "Follows bit.ly/t.co redirects",
  },
};

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function el(tag, className, textContent) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (textContent !== undefined) n.textContent = textContent;
  return n;
}

function icon(svgMarkup, className = "") {
  const span = document.createElement("span");
  if (className) span.className = className;
  span.innerHTML = svgMarkup;
  return span;
}

export function setLoading(containerEl) {
  containerEl.replaceChildren();
  const box = el("div", "pg-loading");
  box.setAttribute("role", "status");
  const spinner = el("span", "pg-loading-spinner");
  spinner.setAttribute("aria-hidden", "true");
  const msg = el("span", "", "Running multi-source threat analysis…");
  box.append(spinner, msg);
  containerEl.appendChild(box);
}

export function renderError(containerEl, message) {
  containerEl.replaceChildren();
  const box = el("div", "pg-error-box", message || "Something went wrong. Please try again.");
  box.setAttribute("role", "alert");
  containerEl.appendChild(box);
}

function renderHeader(verdict, score) {
  const meta = VERDICT_META[verdict] ?? VERDICT_META.suspicious;

  const head = el("div", "pg-verdict-head");
  const iconEl = icon(meta.icon, "pg-verdict-icon");
  iconEl.setAttribute("aria-hidden", "true");
  const textWrap = el("div", "");
  textWrap.appendChild(el("div", "pg-verdict-label", "Threat verdict"));
  textWrap.appendChild(el("div", "pg-verdict-title", meta.label));
  head.append(iconEl, textWrap);

  const scoreRow = el("div", "pg-score-row");
  scoreRow.appendChild(el("span", "", "Risk score"));
  scoreRow.appendChild(el("span", "pg-score-value", `${score} / 100`));

  const track = el("div", "pg-score-track");
  const fill = el("div", "pg-score-fill");
  fill.style.width = `${Math.max(0, Math.min(score, 100))}%`;
  track.appendChild(fill);

  const wrap = el("div", "");
  wrap.append(head, scoreRow, track);
  return wrap;
}

function renderExpansion(original, expanded) {
  const box = el("div", "pg-expansion");
  box.appendChild(el("div", "pg-expansion-title", "SHORTENED LINK — EXPANDED"));
  const from = el("span", "pg-expansion-line from", `from: ${original}`);
  const to = el("span", "pg-expansion-line", `→ ${expanded}`);
  box.append(from, to);
  return box;
}

function renderRecommendation(text) {
  return el("div", "pg-recommendation", text ?? "");
}

function chipForSignal(signal) {
  if (!signal.available) return { text: "unavailable", cls: "" };
  const score = Number(signal.score) || 0;
  if (score >= 60) return { text: `score ${score}`, cls: "bad" };
  if (score >= 25) return { text: `score ${score}`, cls: "warn" };
  return { text: `score ${score}`, cls: "good" };
}

function renderSignal(signal) {
  const meta = SOURCE_META[signal.source] ?? { label: signal.source, desc: "" };
  const li = el("article", `pg-signal ${signal.available ? "available" : ""}`);

  const head = el("div", "pg-signal-head");
  const titleWrap = el("div", "pg-signal-title");
  titleWrap.appendChild(el("span", "pg-signal-dot"));
  titleWrap.appendChild(el("span", "", meta.label));
  const chip = chipForSignal(signal);
  const chipEl = el("span", `pg-chip ${chip.cls}`, chip.text);
  head.append(titleWrap, chipEl);

  const desc = el("p", "pg-signal-desc", meta.desc);

  li.append(head, desc);

  if (Array.isArray(signal.reasons) && signal.reasons.length > 0) {
    const ul = el("ul", "pg-signal-reasons");
    for (const r of signal.reasons) {
      ul.appendChild(el("li", "", r));
    }
    li.appendChild(ul);
  }
  return li;
}

function renderSignalsSection(signals) {
  if (!Array.isArray(signals) || signals.length === 0) return null;

  const wrap = el("section", "");
  const head = el("div", "pg-section-head");
  head.appendChild(el("h3", "pg-section-title", "Detection sources"));
  const avail = signals.filter((s) => s.available).length;
  head.appendChild(el("span", "pg-chip", `${avail}/${signals.length} responded`));
  wrap.appendChild(head);

  const grid = el("div", "pg-signal-grid");
  for (const s of signals) grid.appendChild(renderSignal(s));
  wrap.appendChild(grid);
  return wrap;
}

function renderActions(verdict) {
  const tips = {
    safe: [
      "Still confirm unexpected messages with the sender before acting.",
      "Hover over links to inspect the real destination.",
    ],
    suspicious: [
      "Do not enter credentials, payment, or personal info.",
      "Contact the sender through a channel you already trust — not the one in the message.",
      "If in doubt, don't click.",
    ],
    dangerous: [
      "Do NOT click any link or open any attachment.",
      "If you already entered credentials, change your password from a different device immediately.",
      "Report the message (mark as phishing) and delete it.",
    ],
  };
  const box = el("div", "pg-actions");
  box.appendChild(el("div", "pg-actions-title", "Recommended actions"));
  const ul = el("ul", "");
  for (const t of tips[verdict] ?? tips.suspicious) ul.appendChild(el("li", "", t));
  box.appendChild(ul);
  return box;
}

function renderMeta(signals, totalMs) {
  if (!Array.isArray(signals) || signals.length === 0) return null;
  const wrap = el("footer", "pg-meta");
  wrap.appendChild(el("span", "", `ts: ${new Date().toISOString()}`));
  if (totalMs) wrap.appendChild(el("span", "", `dur: ${totalMs}ms`));
  wrap.appendChild(el("span", "", `engine: phishguard v1.0`));
  return wrap;
}

export function renderResult(containerEl, result) {
  containerEl.replaceChildren();
  const verdict = result.verdict || "suspicious";

  const card = el("article", `pg-verdict ${verdict}`);
  card.setAttribute("aria-live", "polite");

  card.appendChild(renderHeader(verdict, Number(result.score) || 0));

  if (
    result.expanded_url &&
    result.original_url &&
    result.expanded_url !== result.original_url
  ) {
    card.appendChild(renderExpansion(result.original_url, result.expanded_url));
  }

  card.appendChild(renderRecommendation(result.recommendation));

  const signalsSection = renderSignalsSection(result.signals);
  if (signalsSection) card.appendChild(signalsSection);

  card.appendChild(renderActions(verdict));

  const meta = renderMeta(result.signals, result.total_duration_ms);
  if (meta) card.appendChild(meta);

  containerEl.appendChild(card);
}

export function switchTab(activeTabId) {
  const tabs = [
    { tab: "tab-url", panel: "panel-url" },
    { tab: "tab-email-address", panel: "panel-email-address" },
    { tab: "tab-email", panel: "panel-email" },
  ];
  for (const { tab, panel } of tabs) {
    const tabEl = document.getElementById(tab);
    const panelEl = document.getElementById(panel);
    const isActive = tab === activeTabId;
    tabEl.setAttribute("aria-selected", String(isActive));
    panelEl.hidden = !isActive;
  }
  const resultEl = document.getElementById("result-area");
  if (resultEl) resultEl.replaceChildren();
}

// Error visibility helper — replaces the old hidden-class toggling so it works
// with the new `[hidden]` attribute styling in custom.css.
export function showInlineError(errorEl, message) {
  if (!errorEl) return;
  if (message) {
    errorEl.textContent = message;
    errorEl.hidden = false;
  } else {
    errorEl.textContent = "";
    errorEl.hidden = true;
  }
}
