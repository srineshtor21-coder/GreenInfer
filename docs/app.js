/* ============================================================
   GreenInfer — Shared JS
   All pages load this. Handles: theme, nav, scroll, counters.
============================================================ */

// ── Theme toggle (shared across ALL pages) ──
function initTheme() {
  const btn   = document.getElementById('theme-btn');
  const saved = localStorage.getItem('gi-theme');
  if (saved === 'light') {
    document.body.classList.add('light');
    if (btn) btn.textContent = '🌙 Dark';
  }
  if (!btn) return;
  btn.addEventListener('click', () => {
    document.body.classList.toggle('light');
    const isLight = document.body.classList.contains('light');
    localStorage.setItem('gi-theme', isLight ? 'light' : 'dark');
    btn.textContent = isLight ? '🌙 Dark' : '☀️ Light';
  });
}

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
  const toggle   = document.getElementById('nav-toggle');
  const navLinks = document.querySelector('.nav-links');
  if (!toggle || !navLinks) return;
  toggle.addEventListener('click', () => {
    const open = navLinks.style.display === 'flex';
    navLinks.style.display = open ? 'none' : 'flex';
    if (!open) {
      Object.assign(navLinks.style, {
        flexDirection: 'column',
        position: 'fixed',
        top: '64px',
        left: '0',
        right: '0',
        background: 'rgba(8,13,14,0.98)',
        padding: '16px',
        borderBottom: '1px solid rgba(0,255,160,0.1)',
        zIndex: '999'
      });
    }
  });
}

// ── Scroll reveal animations ──
function initScrollAnimations() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.style.opacity = '1';
        e.target.style.transform = 'translateY(0)';
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.08, rootMargin: '0px 0px -30px 0px' });

  document.querySelectorAll('.scroll-reveal').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(24px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
  });
}

// ── Counter animation ──
function animateCounter(el, target, duration, suffix) {
  duration = duration || 1800;
  suffix   = suffix   || '';
  const start   = performance.now();
  const isFloat = target % 1 !== 0;
  const update  = (now) => {
    const progress = Math.min((now - start) / duration, 1);
    const ease     = 1 - Math.pow(1 - progress, 3);
    const val      = ease * target;
    el.textContent = (isFloat ? val.toFixed(1) : Math.floor(val).toLocaleString()) + suffix;
    if (progress < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

function initCounters() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        const el     = e.target;
        const target = parseFloat(el.dataset.target);
        const suffix = el.dataset.suffix || '';
        animateCounter(el, target, 1800, suffix);
        observer.unobserve(el);
      }
    });
  }, { threshold: 0.5 });
  document.querySelectorAll('.counter').forEach(el => observer.observe(el));
}

// ── Tooltip ──
function initTooltips() {
  document.querySelectorAll('[data-tooltip]').forEach(el => {
    const tip = document.createElement('div');
    tip.className = 'gi-tooltip';
    tip.textContent = el.dataset.tooltip;
    tip.style.cssText = [
      'position:absolute','background:#1a272b','color:#e8f5f0',
      "font-size:0.78rem","font-family:'JetBrains Mono',monospace",
      'padding:6px 10px','border-radius:6px','white-space:nowrap',
      'border:1px solid rgba(0,255,160,0.2)','z-index:100',
      'pointer-events:none','opacity:0','transition:opacity 0.15s'
    ].join(';');
    document.body.appendChild(tip);
    el.addEventListener('mouseenter', () => {
      const r = el.getBoundingClientRect();
      tip.style.left  = r.left + 'px';
      tip.style.top   = (r.top - 36 + window.scrollY) + 'px';
      tip.style.opacity = '1';
    });
    el.addEventListener('mouseleave', () => { tip.style.opacity = '0'; });
  });
}

// ── Energy formatter utilities ──
function formatEnergy(wh) {
  if (wh < 1) return (wh * 1000).toFixed(2) + ' mWh';
  return wh.toFixed(3) + ' Wh';
}
function formatCO2(g) {
  if (g < 1) return (g * 1000).toFixed(2) + ' mg';
  return g.toFixed(3) + ' g CO\u2082';
}

// ── Init all (runs on every page) ──
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  setActiveNav();
  initMobileNav();
  initScrollAnimations();
  initCounters();
  initTooltips();
});
