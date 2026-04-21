// Entry point — wires the forms to the API module and the renderer.

import { ApiError, checkEmail, checkEmailAddress, checkUrl } from "./api.js";
import { recordCheck, renderHistory } from "./history.js";
import {
  renderError,
  renderResult,
  setLoading,
  showInlineError,
  switchTab,
} from "./ui.js";
import {
  validateEmailAddressInput,
  validateEmailInput,
  validateUrlInput,
} from "./validators.js";

const $ = (id) => document.getElementById(id);

async function runWithButton(submitEl, containerEl, fn, historyMeta) {
  submitEl.disabled = true;
  setLoading(containerEl);
  try {
    const result = await fn();
    renderResult(containerEl, result);
    if (historyMeta) {
      recordCheck({
        kind: historyMeta.kind,
        input: historyMeta.input,
        result,
      });
    }
  } catch (err) {
    const message =
      err instanceof ApiError
        ? err.message
        : "We couldn't reach the analyzer. Please try again.";
    renderError(containerEl, message);
  } finally {
    submitEl.disabled = false;
  }
}

function wireUrlForm(resultEl) {
  const form = $("url-form");
  const input = $("url-input");
  const submit = $("url-submit");
  const errorEl = $("url-error");

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const value = input.value.trim();
    const error = validateUrlInput(value);
    showInlineError(errorEl, error);
    if (error) return;
    void runWithButton(
      submit,
      resultEl,
      () => checkUrl(value),
      { kind: "url", input: value },
    );
  });
}

function wireEmailForm(resultEl) {
  const form = $("email-form");
  const subject = $("email-subject");
  const sender = $("email-sender");
  const body = $("email-body");
  const submit = $("email-submit");
  const errorEl = $("email-error");

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const payload = {
      subject: subject.value.trim(),
      sender: sender.value.trim(),
      body: body.value.trim(),
    };
    const error = validateEmailInput(payload);
    showInlineError(errorEl, error);
    if (error) return;
    void runWithButton(
      submit,
      resultEl,
      () => checkEmail(payload),
      { kind: "email", input: payload.subject || payload.sender || "(email body)" },
    );
  });
}

function wireEmailAddressForm(resultEl) {
  const form = $("email-address-form");
  const input = $("email-address-input");
  const submit = $("email-address-submit");
  const errorEl = $("email-address-error");

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const value = input.value.trim();
    const error = validateEmailAddressInput(value);
    showInlineError(errorEl, error);
    if (error) return;
    void runWithButton(
      submit,
      resultEl,
      () => checkEmailAddress(value),
      { kind: "email_address", input: value },
    );
  });
}

function wireTabs() {
  $("tab-url").addEventListener("click", () => switchTab("tab-url"));
  $("tab-email-address").addEventListener("click", () =>
    switchTab("tab-email-address"),
  );
  $("tab-email").addEventListener("click", () => switchTab("tab-email"));
}

function init() {
  const resultEl = $("result-area");
  wireTabs();
  wireUrlForm(resultEl);
  wireEmailAddressForm(resultEl);
  wireEmailForm(resultEl);
  renderHistory();
}

init();
