// Local-only scan history. Stays in the browser, never leaves the device.
//
// Each entry stores the full verdict result so clicking an item re-renders
// the detailed card instantly, no backend round-trip.

import { renderResult } from "./ui.js";

const STORAGE_KEY = "phishguard.history.v2";
const MAX_ITEMS = 20;

const KIND_LABEL = {
  url: "URL",
  email_address: "Address",
  email: "Email",
};

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const items = JSON.parse(raw);
    return Array.isArray(items) ? items : [];
  } catch {
    return [];
  }
}

function save(items) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_ITEMS)));
  } catch {
    // Storage might be disabled (private mode) — fail silently.
  }
}

function shorten(text, max = 70) {
  if (!text) return "";
  return text.length > max ? text.slice(0, max - 1) + "…" : text;
}

function relativeTime(iso) {
  const then = new Date(iso).getTime();
  const diff = Math.max(0, Date.now() - then);
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  return `${day}d ago`;
}

export function recordCheck({ kind, input, result }) {
  if (!input || !result) return;
  const items = load();
  const entry = {
    kind,
    input,
    verdict: result.verdict,
    score: Number(result.score) || 0,
    at: new Date().toISOString(),
    result,
  };
  const filtered = items.filter((i) => !(i.kind === kind && i.input === input));
  filtered.unshift(entry);
  save(filtered);
  renderHistory();
}

export function clearHistory() {
  save([]);
  renderHistory();
}

function showEntryDetails(entry) {
  const resultEl = document.getElementById("result-area");
  if (!resultEl) return;
  renderResult(resultEl, entry.result);
  // Smooth-scroll up to the card so the user sees the verdict.
  resultEl.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function renderHistory() {
  const container = document.getElementById("history-area");
  if (!container) return;

  const items = load();
  container.replaceChildren();
  if (items.length === 0) {
    container.hidden = true;
    return;
  }
  container.hidden = false;

  const head = document.createElement("div");
  head.className = "pg-history-head";
  const title = document.createElement("h2");
  title.className = "pg-history-title";
  title.textContent = `Recent scans · ${items.length}`;
  const clear = document.createElement("button");
  clear.type = "button";
  clear.className = "pg-history-clear";
  clear.textContent = "Clear history";
  clear.addEventListener("click", () => clearHistory());
  head.append(title, clear);
  container.appendChild(head);

  const hint = document.createElement("p");
  hint.className = "pg-history-hint";
  hint.textContent = "Tap any entry to see the full report.";
  container.appendChild(hint);

  const list = document.createElement("ul");
  list.className = "pg-history-list";
  for (const item of items) {
    const li = document.createElement("li");
    li.className = "pg-history-item";
    li.setAttribute("role", "button");
    li.setAttribute("tabindex", "0");
    li.setAttribute("aria-label", `View details for ${item.verdict} ${KIND_LABEL[item.kind] ?? item.kind} scan of ${item.input}`);

    const left = document.createElement("div");
    left.className = "pg-history-left";

    const badge = document.createElement("span");
    badge.className = `pg-history-badge ${item.verdict}`;
    badge.textContent = item.verdict;

    const kindEl = document.createElement("span");
    kindEl.className = "pg-kind-chip";
    kindEl.textContent = KIND_LABEL[item.kind] ?? item.kind;

    const inputEl = document.createElement("span");
    inputEl.className = "pg-history-input";
    inputEl.title = item.input;
    inputEl.textContent = shorten(item.input);

    left.append(badge, kindEl, inputEl);

    const right = document.createElement("div");
    right.className = "pg-history-right";
    const scoreEl = document.createElement("span");
    scoreEl.textContent = `${item.score}/100`;
    const whenEl = document.createElement("span");
    whenEl.textContent = relativeTime(item.at);
    const chevron = document.createElement("span");
    chevron.className = "pg-history-chevron";
    chevron.setAttribute("aria-hidden", "true");
    chevron.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>`;
    right.append(scoreEl, whenEl, chevron);

    li.append(left, right);

    // Click / keyboard activation — old entries without `result` gracefully
    // fall back to doing nothing (they'd need a re-scan).
    const activate = () => {
      if (item.result) showEntryDetails(item);
    };
    li.addEventListener("click", activate);
    li.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        activate();
      }
    });

    list.appendChild(li);
  }
  container.appendChild(list);
}
