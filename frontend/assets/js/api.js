// All backend calls live here. UI code never calls fetch directly.

const DEFAULT_API_BASE = "http://127.0.0.1:8000/api/v1";

export const API_BASE = window.__HELIX_API_BASE__ ?? DEFAULT_API_BASE;

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function postJson(path, payload) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // swallow — use the default detail
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export async function checkUrl(url) {
  return postJson("/check/url", { url });
}

export async function checkEmail({ subject, sender, body }) {
  return postJson("/check/email", { subject, sender, body });
}

export async function checkEmailAddress(email) {
  return postJson("/check/email-address", { email });
}

export async function rewriteText({ text, tone }) {
  return postJson("/writing/rewrite", { text, tone });
}

export async function reviewCode({ code, language, context }) {
  return postJson("/code/review", { code, language, context });
}

export async function analyzeImage({ imageDataUrl, filename }) {
  return postJson("/image/analyze", { image_data_url: imageDataUrl, filename });
}

export async function summarizeData({ data, context }) {
  return postJson("/data/summarize", { data, context });
}

export async function translateText({ text, source, target, formality, preserveTone }) {
  return postJson("/translate", {
    text,
    source,
    target,
    formality,
    preserve_tone: preserveTone ?? true,
  });
}
