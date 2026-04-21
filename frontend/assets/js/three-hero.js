// Hero scene — morphing organic blob.
//
// A single closed shape with a wavy edge driven by layered sines. The shape
// slowly rotates and breathes; a soft radial glow surrounds it and small
// satellite dots orbit at random phases. Reads as an ambient "AI thought
// forming" centerpiece.
//
// Dark-blue palette on pure black.

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const POINTS = 96;              // samples around the blob perimeter
const SAT_COUNT = 7;            // orbiting satellite dots
const SPIN_RATE = 0.06;         // radians per second

const COLOR_FILL_INNER = "rgba(111, 163, 224, 0.28)";
const COLOR_FILL_OUTER = "rgba(111, 163, 224, 0)";
const COLOR_STROKE = "rgba(180, 210, 255, 0.55)";
const COLOR_GLOW = "rgba(111, 163, 224, 0.25)";
const COLOR_CORE = "#c8e1ff";
const COLOR_SATELLITE = "#a9d3ff";

function init() {
  const existing = document.querySelector("[data-three-hero]");
  if (!existing) return;
  const container = existing.parentElement;

  const canvas = document.createElement("canvas");
  canvas.setAttribute("data-three-hero", "");
  existing.replaceWith(canvas);

  const ctx = canvas.getContext("2d", { alpha: true });
  if (!ctx) return;
  window.__heroScene = "morphing-blob";

  let cssW = 0;
  let cssH = 0;
  let dpr = 1;
  let cx = 0;
  let cy = 0;
  let baseRadius = 0;

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    cssW = container.clientWidth || window.innerWidth;
    cssH = container.clientHeight || 480;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    canvas.style.width = `${cssW}px`;
    canvas.style.height = `${cssH}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cx = cssW * 0.5;
    cy = cssH * 0.5;
    baseRadius = Math.min(cssW, cssH) * 0.17;
  }
  resize();
  window.addEventListener("resize", resize);

  // Mouse drifts the centre + adds a tiny bias to the blob shape.
  const mouseTarget = { x: 0, y: 0 };
  const mouse = { x: 0, y: 0 };
  window.addEventListener("mousemove", (event) => {
    mouseTarget.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouseTarget.y = -((event.clientY / window.innerHeight) * 2 - 1);
  }, { passive: true });

  let visible = true;
  const io = new IntersectionObserver(
    ([entry]) => { visible = entry.isIntersecting; },
    { threshold: 0.05 },
  );
  io.observe(canvas);

  // Satellites — each has a unique radius, phase and speed.
  const satellites = [];
  for (let i = 0; i < SAT_COUNT; i++) {
    satellites.push({
      radiusMult: 1.35 + Math.random() * 0.55,     // fraction of baseRadius
      phase: Math.random() * Math.PI * 2,
      speed: (Math.random() < 0.5 ? -1 : 1) * (0.12 + Math.random() * 0.18),
      size: 1.6 + Math.random() * 1.4,
    });
  }

  /**
   * Layered sine deformation for the blob's radius at a given angle + time.
   * Returns a multiplier on baseRadius (roughly 0.75..1.25).
   */
  function edgeRadius(angle, t, mouseBias) {
    const a = angle;
    const d =
      Math.sin(a * 2 + t * 0.55) * 0.18 +
      Math.sin(a * 3 - t * 0.75) * 0.12 +
      Math.cos(a * 5 + t * 1.05) * 0.08 +
      Math.cos(a * 7 - t * 0.35) * 0.05;
    // Mouse gives the blob a gentle pull in one direction.
    const pull = Math.cos(a - mouseBias.angle) * mouseBias.magnitude;
    return 1 + d + pull;
  }

  function frame(now) {
    requestAnimationFrame(frame);
    window.__heroLastFrameAt = performance.now();
    window.__heroFrameCount = (window.__heroFrameCount || 0) + 1;
    if (!visible) return;

    const speedMult = reduceMotion ? 0.25 : 1;
    const t = (now / 1000) * speedMult;

    mouse.x += (mouseTarget.x - mouse.x) * 0.05;
    mouse.y += (mouseTarget.y - mouse.y) * 0.05;
    cx = cssW * 0.5 + mouse.x * cssW * 0.03;
    cy = cssH * 0.5 - mouse.y * cssH * 0.025;

    const mouseBias = {
      angle: Math.atan2(-mouse.y, mouse.x),
      magnitude: Math.hypot(mouse.x, mouse.y) * 0.06,
    };
    const spin = t * SPIN_RATE;

    ctx.clearRect(0, 0, cssW, cssH);

    // 1. Outer glow.
    const glow = ctx.createRadialGradient(cx, cy, baseRadius * 0.6, cx, cy, baseRadius * 2.2);
    glow.addColorStop(0, COLOR_GLOW);
    glow.addColorStop(1, "rgba(111, 163, 224, 0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(cx, cy, baseRadius * 2.2, 0, Math.PI * 2);
    ctx.fill();

    // 2. Blob path — sample N points around the edge with edgeRadius().
    const samples = [];
    for (let i = 0; i < POINTS; i++) {
      const angle = (i / POINTS) * Math.PI * 2 + spin;
      const r = baseRadius * edgeRadius(angle, t, mouseBias);
      samples.push({
        x: cx + Math.cos(angle) * r,
        y: cy + Math.sin(angle) * r,
      });
    }

    // Smooth the path using quadratic curves through midpoints for a liquid look.
    ctx.beginPath();
    const mid = (a, b) => ({ x: (a.x + b.x) * 0.5, y: (a.y + b.y) * 0.5 });
    const first = mid(samples[POINTS - 1], samples[0]);
    ctx.moveTo(first.x, first.y);
    for (let i = 0; i < POINTS; i++) {
      const curr = samples[i];
      const next = samples[(i + 1) % POINTS];
      const m = mid(curr, next);
      ctx.quadraticCurveTo(curr.x, curr.y, m.x, m.y);
    }
    ctx.closePath();

    // 3. Fill the blob with a radial gradient.
    const fill = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseRadius * 1.4);
    fill.addColorStop(0, COLOR_FILL_INNER);
    fill.addColorStop(1, COLOR_FILL_OUTER);
    ctx.fillStyle = fill;
    ctx.fill();

    // 4. Stroke the edge.
    ctx.strokeStyle = COLOR_STROKE;
    ctx.lineWidth = 1.6;
    ctx.stroke();

    // 5. Core glow + bright dot.
    const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseRadius * 0.45);
    core.addColorStop(0, "rgba(200, 225, 255, 0.5)");
    core.addColorStop(1, "rgba(200, 225, 255, 0)");
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(cx, cy, baseRadius * 0.45, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = COLOR_CORE;
    ctx.beginPath();
    ctx.arc(cx, cy, 3.2, 0, Math.PI * 2);
    ctx.fill();

    // 6. Orbiting satellite dots.
    for (const s of satellites) {
      const a = s.phase + t * s.speed;
      const r = baseRadius * s.radiusMult;
      const sx = cx + Math.cos(a) * r;
      const sy = cy + Math.sin(a) * r;

      // Soft glow around each satellite.
      const sg = ctx.createRadialGradient(sx, sy, 0, sx, sy, 10);
      sg.addColorStop(0, "rgba(111, 163, 224, 0.4)");
      sg.addColorStop(1, "rgba(111, 163, 224, 0)");
      ctx.fillStyle = sg;
      ctx.beginPath();
      ctx.arc(sx, sy, 10, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = COLOR_SATELLITE;
      ctx.beginPath();
      ctx.arc(sx, sy, s.size, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  requestAnimationFrame(frame);
  setInterval(() => {
    const last = window.__heroLastFrameAt || 0;
    if (performance.now() - last > 120) frame(performance.now());
  }, 1000 / 30);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
