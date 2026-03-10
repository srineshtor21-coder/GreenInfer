/* ============================================================
   GreenInfer — Shared JS
   ============================================================ */

// ── Nav active state ──
function setActiveNav() {
  const path = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a').forEach(a => {
    const href = a.getAttribute('href');
    if (href === path || (path === '' && href === 'index.html')) {
      a.classList.add('active');
    }
  });
}

// ── Mobile nav toggle ──
function initMobileNav() {
  const toggle = document.getElementById('nav-toggle');
  const navLinks = document.querySelector('.nav-links');
  if (!toggle) return;
  toggle.addEventListener('click', () => {
    navLinks.style.display = navLinks.style.display === 'flex' ? 'none' : 'flex';
    navLinks.style.flexDirection = 'column';
    navLinks.style.position = 'absolute';
    navLinks.style.top = '64px';
    navLinks.style.left = '0';
    navLinks.style.right = '0';
    navLinks.style.background = 'rgba(8,13,14,0.98)';
    navLinks.style.padding = '16px';
    navLinks.style.borderBottom = '1px solid rgba(0,255,160,0.1)';
  });
}

// ── Animate on scroll ──
function initScrollAnimations() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.style.opacity = '1';
        e.target.style.transform = 'translateY(0)';
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

  document.querySelectorAll('.scroll-reveal').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(24px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
  });
}

// ── Counter animation ──
function animateCounter(el, target, duration = 1800, suffix = '') {
  const start = performance.now();
  const isFloat = target % 1 !== 0;
  const update = (now) => {
    const progress = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    const val = ease * target;
    el.textContent = (isFloat ? val.toFixed(1) : Math.floor(val).toLocaleString()) + suffix;
    if (progress < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

function initCounters() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        const el = e.target;
        const target = parseFloat(el.dataset.target);
        const suffix = el.dataset.suffix || '';
        animateCounter(el, target, 1800, suffix);
        observer.unobserve(el);
      }
    });
  }, { threshold: 0.5 });
  document.querySelectorAll('.counter').forEach(el => observer.observe(el));
}

// ── Carbon mode indicator ──
const GRID_INTENSITY = {
  eco: { label: 'Grid: Clean', color: '#00ffa0', bar: 18 },
  moderate: { label: 'Grid: Moderate', color: '#f5a623', bar: 52 },
  high: { label: 'Grid: Heavy', color: '#ff4d6d', bar: 88 }
};

function setGridMode(mode) {
  const data = GRID_INTENSITY[mode];
  const indicator = document.getElementById('grid-indicator');
  const bar = document.getElementById('grid-bar');
  if (indicator) {
    indicator.textContent = data.label;
    indicator.style.color = data.color;
  }
  if (bar) {
    bar.style.width = data.bar + '%';
    bar.style.background = data.color;
  }
}

// ── Tooltip ──
function initTooltips() {
  document.querySelectorAll('[data-tooltip]').forEach(el => {
    const tip = document.createElement('div');
    tip.className = 'tooltip';
    tip.textContent = el.dataset.tooltip;
    tip.style.cssText = `
      position:absolute; background:#1a272b; color:#e8f5f0;
      font-size:0.78rem; font-family:var(--font-mono);
      padding:6px 10px; border-radius:6px; white-space:nowrap;
      border:1px solid rgba(0,255,160,0.2); z-index:100;
      pointer-events:none; opacity:0; transition:opacity 0.15s;
    `;
    document.body.appendChild(tip);
    el.addEventListener('mouseenter', (ev) => {
      const r = el.getBoundingClientRect();
      tip.style.left = r.left + 'px';
      tip.style.top = (r.top - 36 + window.scrollY) + 'px';
      tip.style.opacity = '1';
    });
    el.addEventListener('mouseleave', () => { tip.style.opacity = '0'; });
  });
}

// ── Energy formatter ──
function formatEnergy(wh) {
  if (wh < 1) return (wh * 1000).toFixed(2) + ' mWh';
  return wh.toFixed(3) + ' Wh';
}
function formatCO2(g) {
  if (g < 1) return (g * 1000).toFixed(2) + ' mg';
  return g.toFixed(3) + ' g CO₂';
}

// ── Init all ──
document.addEventListener('DOMContentLoaded', () => {
  setActiveNav();
  initMobileNav();
  initScrollAnimations();
  initCounters();
  initTooltips();
});
