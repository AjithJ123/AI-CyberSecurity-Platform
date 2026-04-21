// Client-side validation. Backend validates again — this exists for fast UX feedback.

export const MAX_URL_LENGTH = 2048;
export const MAX_EMAIL_BODY_LENGTH = 10_000;

export function isValidUrl(value) {
  try {
    const u = new URL(value);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

export function validateUrlInput(value) {
  const trimmed = (value ?? "").trim();
  if (!trimmed) return "Please enter a URL to check.";
  if (trimmed.length > MAX_URL_LENGTH) return "That URL is too long.";
  if (!isValidUrl(trimmed)) return "Please enter a valid http:// or https:// URL.";
  return null;
}

export function validateEmailInput({ body }) {
  const b = (body ?? "").trim();
  if (!b) return "Please paste the email body.";
  if (b.length > MAX_EMAIL_BODY_LENGTH) return "Email body is too long.";
  return null;
}

export function validateEmailAddressInput(value) {
  const v = (value ?? "").trim();
  if (!v) return "Please enter an email address.";
  if (v.length > 320) return "Email address is too long.";
  // Light format check — backend does the real work.
  if (!/^\S+@\S+\.\S+$/.test(v)) return "That doesn't look like a valid email address.";
  return null;
}
