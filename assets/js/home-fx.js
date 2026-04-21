// Home-page visual FX:
//   - scroll progress bar
//   - reveal-on-scroll for sections (IntersectionObserver, fade + slide-up)
//   - mouse-tracked 3D tilt on service cards
//   - subtle parallax on banner blobs based on scroll position
//   - "scrolled" state on the header for backdrop emphasis
//
// All effects are progressively enhanced — the page is fully usable without JS.

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function initScrollProgress() {
  const bar = document.getElementById("pg-scroll-bar");
  if (!bar) return;
  const update = () => {
    const doc = document.documentElement;
    const max = doc.scrollHeight - doc.clientHeight;
    const pct = max > 0 ? (doc.scrollTop / max) * 100 : 0;
    bar.style.transform = `scaleX(${pct / 100})`;
  };
  update();
  window.addEventListener("scroll", update, { passive: true });
  window.addEventListener("resize", update);
}

function initRevealOnScroll() {
  const items = document.querySelectorAll("[data-reveal]");
  if (items.length === 0) return;

  if (reduceMotion) {
    items.forEach((el) => el.classList.add("is-revealed"));
    return;
  }

  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-revealed");
          io.unobserve(entry.target);
        }
      }
    },
    { threshold: 0.12, rootMargin: "0px 0px -60px 0px" },
  );
  items.forEach((el) => io.observe(el));
}

function initCardTilt() {
  if (reduceMotion) return;
  const cards = document.querySelectorAll("[data-tilt]");
  for (const card of cards) {
    let raf = 0;
    const onMove = (event) => {
      const rect = card.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width;
      const y = (event.clientY - rect.top) / rect.height;
      const rotY = (x - 0.5) * 14; // -7..7deg
      const rotX = (0.5 - y) * 14;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        card.style.setProperty("--tilt-x", `${rotX}deg`);
        card.style.setProperty("--tilt-y", `${rotY}deg`);
        card.style.setProperty("--tilt-shine-x", `${x * 100}%`);
        card.style.setProperty("--tilt-shine-y", `${y * 100}%`);
      });
    };
    const onLeave = () => {
      cancelAnimationFrame(raf);
      card.style.setProperty("--tilt-x", `0deg`);
      card.style.setProperty("--tilt-y", `0deg`);
    };
    card.addEventListener("mousemove", onMove);
    card.addEventListener("mouseleave", onLeave);
  }
}

function initBannerParallax() {
  if (reduceMotion) return;
  const blobs = document.querySelectorAll(".pg-blob");
  if (blobs.length === 0) return;

  let raf = 0;
  const onScroll = () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const y = window.scrollY;
      blobs.forEach((blob, i) => {
        const speed = (i + 1) * 0.08;
        blob.style.translate = `0 ${-y * speed}px`;
      });
    });
  };
  window.addEventListener("scroll", onScroll, { passive: true });
}

function initHeaderScrolled() {
  const header = document.querySelector(".pg-header");
  if (!header) return;
  const update = () => {
    if (window.scrollY > 12) header.classList.add("is-scrolled");
    else header.classList.remove("is-scrolled");
  };
  update();
  window.addEventListener("scroll", update, { passive: true });
}

// One-shot text scramble — cycles through random characters before settling
// on each final letter. Runs once when the element first becomes visible.
function initScramble() {
  if (reduceMotion) return;
  const items = document.querySelectorAll("[data-scramble]");
  if (items.length === 0) return;
  const CHARS = "!<>-_\\/[]{}—=+*^?#________";

  const scramble = (el) => {
    const target = el.textContent;
    const length = target.length;
    let frame = 0;
    const totalFrames = 32;

    const tick = () => {
      let out = "";
      for (let i = 0; i < length; i++) {
        const revealAt = (i / length) * (totalFrames * 0.7);
        if (frame >= revealAt) {
          out += target[i];
        } else {
          out += CHARS[Math.floor(Math.random() * CHARS.length)];
        }
      }
      el.textContent = out;
      frame++;
      if (frame <= totalFrames) {
        requestAnimationFrame(tick);
      } else {
        el.textContent = target;
      }
    };
    tick();
  };

  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          scramble(entry.target);
          io.unobserve(entry.target);
        }
      }
    },
    { threshold: 0.5 },
  );
  items.forEach((el) => io.observe(el));
}

function init() {
  initScrollProgress();
  initRevealOnScroll();
  initCardTilt();
  initBannerParallax();
  initHeaderScrolled();
  initScramble();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
