# CLAUDE.md — Frontend (HTML + JavaScript + Tailwind)

Rules for writing frontend code in the `frontend/` folder. Read the root `CLAUDE.md` first.

---

## 1. Stack

- **HTML5** — semantic markup, no div soup.
- **JavaScript** — modern ES2022+, ES modules (`type="module"`). No build step in v1.
- **Tailwind CSS** — via the Play CDN in v1, compiled in v1.5+.
- **No framework** until v1.5. Keep this lean.
- **No jQuery. Ever.**

---

## 2. Folder Structure

```
frontend/
├── index.html              # Landing + scanner
├── about.html
├── privacy.html
├── developers.html
├── assets/
│   ├── js/
│   │   ├── main.js         # Entry point
│   │   ├── api.js          # Backend calls
│   │   ├── ui.js           # DOM updates, result rendering
│   │   └── validators.js   # Client-side input checks
│   ├── css/
│   │   └── custom.css      # Only for things Tailwind can't do
│   └── img/
└── CLAUDE.md               # This file
```

---

## 3. HTML Rules

### 3.1 Semantic markup
Use `<header>`, `<main>`, `<section>`, `<article>`, `<footer>`, `<nav>`. Not nested `<div>` s with class names pretending to be semantic.

```html
<!-- Good -->
<main>
  <section aria-labelledby="scanner-heading">
    <h1 id="scanner-heading">Check a suspicious link</h1>
    <form>...</form>
  </section>
</main>

<!-- Bad -->
<div class="main">
  <div class="section">
    <div class="title">Check a suspicious link</div>
  </div>
</div>
```

### 3.2 Accessibility (non-negotiable)
- Every form input has a `<label>` (visible or `sr-only`).
- Every button has accessible text. Icon-only buttons get `aria-label`.
- Color is never the only signal for verdicts. Always pair with a text label and an icon.
- Contrast ratio: 4.5:1 minimum for body text, 3:1 for large text.
- All interactive elements must be keyboard-reachable.
- Test: you should be able to use the whole app with only the keyboard.

### 3.3 Meta and SEO
Every page needs:
```html
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="...">
<title>Specific page title — PhishGuard AI</title>
```

---

## 4. JavaScript Rules

### 4.1 Modern syntax only
- `const` by default, `let` only when reassigning. Never `var`.
- Arrow functions for callbacks.
- Template literals for string building.
- `async/await`, not `.then()` chains.
- Destructuring for objects and arrays.
- Optional chaining (`?.`) and nullish coalescing (`??`).

### 4.2 ES modules
```html
<script type="module" src="assets/js/main.js"></script>
```
Each file is a module. Use `import` and `export`, not globals.

### 4.3 No global state
No variables on `window`. Pass state through function arguments or keep it in a single module-level object.

### 4.4 Strict equality
Always `===` and `!==`. Never `==`.

### 4.5 Naming
- Variables and functions: `camelCase`.
- Constants (true module-level, never reassigned): `UPPER_SNAKE_CASE`.
- DOM element references: prefix with `$` or `el`. `const $submitBtn = ...` or `const submitBtnEl = ...`. Pick one convention and stick with it.
- Event handlers: `handleXxx` or `onXxx`.

### 4.6 File size
If a `.js` file goes over 200 lines, split it. Probably it's doing too much.

---

## 5. API Calls

### 5.1 One file for all backend calls
All `fetch` calls live in `assets/js/api.js`. UI code never calls `fetch` directly.

```javascript
// api.js
const API_BASE = "/api/v1";

export async function checkUrl(url) {
  const res = await fetch(`${API_BASE}/check/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}
```

### 5.2 Always handle loading and error states
Three states for every async operation: idle, loading, error. Never leave the user staring at a dead UI.

```javascript
setState("loading");
try {
  const result = await checkUrl(url);
  renderResult(result);
} catch (err) {
  renderError(err);
}
```

### 5.3 Never expose API keys in the frontend
If a call needs a key, it must go through our backend, not direct from the browser.

---

## 6. Styling (Tailwind)

### 6.1 Use utility classes
Prefer Tailwind utilities over custom CSS.

```html
<!-- Good -->
<button class="rounded-lg bg-blue-600 px-6 py-3 text-white hover:bg-blue-700">
  Analyze
</button>
```

### 6.2 Extract repeated patterns
If the same long class list appears 3+ times, either:
- Extract to a CSS class in `custom.css` using `@apply` (once we have a build step), or
- Extract to a small JS render function.

### 6.3 Design tokens
Use Tailwind's built-in scale. Don't invent new sizes.
- Spacing: `p-4`, `p-6`, `p-8` — not `p-5` everywhere.
- Colors: stick to a small palette. Primary blue, neutral grays, semantic red/amber/green.

### 6.4 Verdict colors
| Verdict | Background | Border | Text |
|---------|-----------|--------|------|
| Safe | `bg-green-50` | `border-green-500` | `text-green-900` |
| Suspicious | `bg-amber-50` | `border-amber-500` | `text-amber-900` |
| Dangerous | `bg-red-50` | `border-red-500` | `text-red-900` |

**Always pair color with an icon and a word.** A red box alone is not enough.

### 6.5 Mobile first
Default styles are mobile. Use `sm:`, `md:`, `lg:` to scale up.

```html
<div class="px-4 md:px-8 lg:px-16">...</div>
```

---

## 7. Forms

### 7.1 Client-side validation is for UX, not security
Always validate again on the backend. Client-side checks exist to show errors fast.

### 7.2 URL input validation
```javascript
export function isValidUrl(value) {
  try {
    const u = new URL(value);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}
```

### 7.3 Length limits
- URL input: 2048 characters max.
- Email body input: 10,000 characters max.
Enforce both in the input element (`maxlength`) and in JS before submit.

### 7.4 Disable submit while loading
Prevent double-submits. Re-enable in `finally`.

---

## 8. Privacy in the UI

### 8.1 Warn before sending sensitive content
Above the email input:
> "Do not paste emails containing passwords, OTPs, or personal details. We don't store your input, but please redact sensitive data."

### 8.2 No tracking scripts
No Google Analytics, no Facebook pixel, no Hotjar. Use Plausible or self-hosted Umami if analytics are needed.

### 8.3 Respect Do Not Track
If `navigator.doNotTrack === "1"`, skip all analytics even if configured.

---

## 9. Performance

- Lighthouse score target: 95+ on all four categories.
- No render-blocking resources above 30KB.
- Images must be optimized (WebP where possible, with PNG/JPG fallback).
- Defer non-critical JS with `defer` or `type="module"` (which is deferred by default).

---

## 10. Browser Support

- Modern evergreen browsers: Chrome, Firefox, Safari, Edge — last 2 versions.
- No IE11 support.
- Test on mobile Safari and Chrome Android — that's where most phishing victims will arrive from.

---

## 11. What NOT to Do

- **Don't use `innerHTML` with user input.** Ever. Use `textContent` or create elements and set properties.
- **Don't use inline event handlers** (`onclick="..."`). Attach listeners in JS.
- **Don't pull in a giant library** for something you can do in 10 lines.
- **Don't use `localStorage` for anything sensitive.** It's not secure storage.
- **Don't add custom fonts** that hurt load time. System font stack is fine.
- **Don't rely on hover-only interactions.** Mobile users don't have hover.

---

## 12. Component Patterns (v1 — no framework)

Since we have no framework, components are plain functions that return DOM nodes or HTML strings.

```javascript
// ui.js
export function renderVerdictCard(result) {
  const card = document.createElement("div");
  card.className = verdictClasses(result.verdict);
  card.innerHTML = `
    <h2 class="text-2xl font-bold">${escapeHtml(result.verdict.toUpperCase())}</h2>
    <p class="mt-2">${escapeHtml(result.recommendation)}</p>
    <ul class="mt-4 list-disc pl-6">
      ${result.reasons.map(r => `<li>${escapeHtml(r)}</li>`).join("")}
    </ul>
  `;
  return card;
}
```

**Always escape HTML** when inserting any backend data. Never trust that it's safe.

```javascript
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
```

---

## 13. When Adding a New Page

1. Copy `index.html` as a starting template (keeps header/footer consistent).
2. Update `<title>` and `<meta name="description">`.
3. Link it from the main nav if it's user-facing.
4. Run Lighthouse — don't ship if any score is below 90.
5. Test with keyboard-only navigation.
