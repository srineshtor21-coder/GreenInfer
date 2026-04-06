

(function GreenInferFix() {
  'use strict';

  /* ── 1. FIX SEND ARROW (runs immediately on DOM ready) ── */
  function fixSendArrow() {
    const btn = document.getElementById('send-btn');
    if (!btn) return;
    btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
    </svg>`;
  }

  /* ── 2. STREAMING ANIMATION CSS ── */
  function injectCSS() {
    const style = document.createElement('style');
    style.textContent = `
      /* Streaming cursor blink */
      @keyframes gi-cursor { 0%,100%{opacity:1} 50%{opacity:0} }
      .gi-cursor {
        display:inline-block; width:2px; height:1.05em;
        background:var(--green-core, #00ffa0);
        margin-left:2px; vertical-align:text-bottom;
        animation:gi-cursor .85s infinite;
      }

      /* Rich thinking bubble */
      @keyframes gi-think-slide { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
      .gi-thinking {
        display:flex; align-items:center; gap:10px;
        padding:10px 14px; margin:3px 18px;
        background:var(--bg-surface, #111c1e);
        border:1px solid var(--border, rgba(0,255,160,.08));
        border-radius:var(--radius-md, 12px);
        font-family:var(--font-mono, monospace); font-size:.78rem;
        animation:gi-think-slide .18s ease;
        border-left:2px solid var(--green-core, #00ffa0);
      }
      .gi-think-dots { display:flex; gap:3px; align-items:center; flex-shrink:0; }
      .gi-think-dot {
        width:4px; height:4px; border-radius:50%;
        animation:blink 1.1s ease-in-out infinite;
      }
      .gi-think-dot:nth-child(1) { background:var(--green-core,#00ffa0); animation-delay:0s; }
      .gi-think-dot:nth-child(2) { background:var(--teal-accent,#00e5cc); animation-delay:.18s; }
      .gi-think-dot:nth-child(3) { background:var(--amber-warn,#f5a623); animation-delay:.36s; }
      .gi-think-status { color:var(--text-muted,#4a7068); font-size:.71rem; transition:opacity .2s; }
      .gi-step-trail { display:flex; gap:4px; flex-wrap:wrap; }
      .gi-step { font-size:.62rem; padding:1px 5px; background:rgba(0,255,160,.06); border:1px solid rgba(0,255,160,.12); border-radius:99px; color:var(--green-core,#00ffa0); opacity:0; transition:opacity .3s; }
      .gi-step.done { opacity:1; }

      /* Light mode user bubble fix */
      body.light .msg-wrap.user .msg-body {
        background:rgba(0,95,53,.14) !important;
        border-color:rgba(0,95,53,.28) !important;
        color:var(--text-primary) !important;
      }

      /* Meta reveal animation */
      .gi-meta-hidden { opacity:0; transform:translateY(4px); transition:opacity .3s ease, transform .3s ease; }
      .gi-meta-shown { opacity:1; transform:translateY(0); }
    `;
    document.head.appendChild(style);
  }

  /* ── 3. THINKING BUBBLE ── */
  const STEPS = [
    { emoji: '🔬', label: 'Scoring complexity...' },
    { emoji: '⚡', label: 'Running T5 optimizer...' },
    { emoji: '🌍', label: 'Checking ERCOT grid...' },
    { emoji: '🎯', label: 'Routing to model tier...' },
    { emoji: '💡', label: 'Generating response...' },
  ];
  const STEP_SHORT = ['Scored','Optimized','Grid OK','Routing'];

  let _thinkEl = null, _thinkTimer = null, _thinkStep = 0;

  function showThinking() {
    hideThinking(); // clear any existing
    _thinkEl = document.createElement('div');
    _thinkEl.id = 'gi-thinking-wrap';
    _thinkEl.className = 'gi-thinking';
    _thinkEl.innerHTML = `
      <span id="gi-think-emoji" style="font-size:.9rem">🔬</span>
      <div class="gi-think-dots">
        <div class="gi-think-dot"></div>
        <div class="gi-think-dot"></div>
        <div class="gi-think-dot"></div>
      </div>
      <span class="gi-think-status" id="gi-think-status">Analyzing query...</span>
      <div class="gi-step-trail" id="gi-step-trail"></div>
    `;
    const msgs = document.getElementById('chat-msgs');
    if (msgs) { msgs.appendChild(_thinkEl); msgs.scrollTo({ top: msgs.scrollHeight, behavior: 'smooth' }); }
    _thinkStep = 0;
    _advanceThink();
  }

  function _advanceThink() {
    if (_thinkStep >= STEPS.length) return;
    const s = STEPS[_thinkStep];
    const emoji = document.getElementById('gi-think-emoji');
    const status = document.getElementById('gi-think-status');
    const trail = document.getElementById('gi-step-trail');
    if (emoji) emoji.textContent = s.emoji;
    if (status) { status.style.opacity = '0'; setTimeout(() => { if (status) { status.textContent = s.label; status.style.opacity = '1'; } }, 150); }
    if (trail && _thinkStep > 0 && STEP_SHORT[_thinkStep - 1]) {
      const badge = document.createElement('span'); badge.className = 'gi-step';
      badge.textContent = STEP_SHORT[_thinkStep - 1]; trail.appendChild(badge);
      setTimeout(() => badge.classList.add('done'), 40);
    }
    _thinkStep++;
    _thinkTimer = setTimeout(_advanceThink, 550 + Math.random() * 350);
  }

  function hideThinking() {
    clearTimeout(_thinkTimer);
    const el = document.getElementById('gi-thinking-wrap');
    if (el) { el.style.opacity = '0'; el.style.transform = 'translateY(-4px)'; el.style.transition = 'all .18s ease'; setTimeout(() => el.remove(), 200); }
    _thinkEl = null;
  }

  /* ── 4. STREAM TEXT INTO ELEMENT ── */
  function streamInto(el, text, onDone) {
    el.innerHTML = '';
    const textSpan = document.createElement('span');
    const cursor = document.createElement('span');
    cursor.className = 'gi-cursor';
    el.appendChild(textSpan);
    el.appendChild(cursor);

    let i = 0;
    const charDelay = () => {
      const ch = text[i] || '';
      if (ch === '\n') return 12;
      if (/[.,!?;:]/.test(ch)) return 45;
      if (ch === ' ') return 22;
      return Math.random() * 14 + 5;
    };

    function tick() {
      if (i < text.length) {
        i++;
        // Render partial text with basic markdown
        textSpan.innerHTML = renderPartialMd(text.slice(0, i));
        // Scroll
        const msgs = document.getElementById('chat-msgs');
        if (msgs) msgs.scrollTo({ top: msgs.scrollHeight, behavior: 'smooth' });
        setTimeout(tick, charDelay());
      } else {
        // Done — render full markdown and remove cursor
        cursor.remove();
        if (typeof renderMd === 'function') {
          textSpan.innerHTML = renderMd(text);
        } else {
          textSpan.innerHTML = renderPartialMd(text);
        }
        // Syntax highlight
        textSpan.querySelectorAll('pre code').forEach(block => {
          if (window.Prism) Prism.highlightElement(block);
          const pre = block.parentElement;
          if (pre && !pre.querySelector('.copy-btn')) {
            pre.style.position = 'relative';
            const cb = document.createElement('button'); cb.className = 'copy-btn'; cb.textContent = 'Copy';
            cb.onclick = () => navigator.clipboard.writeText(block.textContent).then(() => { cb.textContent = 'Copied!'; setTimeout(() => cb.textContent = 'Copy', 1500); });
            pre.appendChild(cb);
          }
        });
        if (onDone) onDone();
      }
    }
    setTimeout(tick, 20);
  }

  function renderPartialMd(text) {
    return text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) =>
        `<pre><code${lang ? ` class="language-${lang}"` : ''}>${code.trim()}</code></pre>`)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/^### (.+)$/gm, '<strong>$1</strong>')
      .replace(/^## (.+)$/gm, '<strong style="font-size:1.02em">$1</strong>')
      .replace(/^# (.+)$/gm, '<strong style="font-size:1.08em">$1</strong>')
      .replace(/^[*-] (.+)$/gm, '<li>$1</li>')
      .replace(/(<li>[\s\S]*?<\/li>)+/g, m => `<ul>${m}</ul>`)
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n/g, '<br/>');
  }

  /* ── 5. PATCH CHAT TO USE RICH THINKING + STREAMING ── */
  function patchChat() {
    // Patch send() to intercept typing indicator
    const origSend = window.send;
    if (typeof origSend !== 'function') {
      setTimeout(patchChat, 100);
      return;
    }

    // Intercept typing indicator show/hide
    const typingEl = document.getElementById('typing-ind');
    if (typingEl) {
      const origAdd = typingEl.classList.add.bind(typingEl.classList);
      const origRemove = typingEl.classList.remove.bind(typingEl.classList);
      typingEl.classList.add = function(...args) {
        if (args.includes('show')) { showThinking(); return; }
        origAdd(...args);
      };
      typingEl.classList.remove = function(...args) {
        if (args.includes('show')) { hideThinking(); return; }
        origRemove(...args);
      };
    }

    // Patch mkAiMsg to add streaming
    const origMkAiMsg = window.mkAiMsg;
    if (typeof origMkAiMsg === 'function') {
      window.mkAiMsg = function(data, gs) {
        const el = origMkAiMsg(data, gs);
        // Find the msg-body and stream into it
        const bodyEl = el.querySelector('.msg-body');
        if (bodyEl && data.response) {
          const fullText = data.response;
          bodyEl.innerHTML = ''; // clear pre-rendered content
          // Animate meta tags in after streaming
          const metaEl = el.querySelector('.inf-meta');
          const effEl = el.querySelector('.eff-toggle');
          const whyBtnEl = el.querySelector('.why-btn');
          const warnEl = el.querySelector('[style*="mWh to regenerate"]');
          [metaEl, effEl, whyBtnEl, warnEl].forEach(e => { if (e) { e.classList.add('gi-meta-hidden'); } });
          streamInto(bodyEl, fullText, () => {
            [metaEl, effEl, whyBtnEl, warnEl].forEach((e, i) => {
              if (e) setTimeout(() => e.classList.add('gi-meta-shown'), i * 80);
            });
          });
        }
        return el;
      };
    }
  }

  /* ── 6. FIX LOGIN/SIGNUP TO REDIRECT TO DASHBOARD ── */
  function patchAuth() {
    const origLogin = window.handleLogin;
    const origSignup = window.handleSignup;

    if (typeof origLogin === 'function') {
      window.handleLogin = function() {
        origLogin();
        // Redirect after modal closes
        setTimeout(() => {
          if (window.S && window.S.user) {
            window.location.href = '/dashboard';
          }
        }, 800);
      };
    }

    if (typeof origSignup === 'function') {
      window.handleSignup = function() {
        origSignup();
        setTimeout(() => {
          if (window.S && window.S.user) {
            window.location.href = '/dashboard';
          }
        }, 800);
      };
    }
  }

  /* ── INIT ── */
  function init() {
    injectCSS();
    fixSendArrow();
    patchChat();
    patchAuth();

    // Re-fix arrow after any re-renders
    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) {
      new MutationObserver(() => fixSendArrow()).observe(sendBtn, { childList: true });
    }

    console.log('%c[GreenInfer] chat-fix.js loaded ✓', 'color:#00ffa0;font-family:monospace');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
