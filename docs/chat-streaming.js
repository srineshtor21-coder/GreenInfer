/* ══════════════════════════════════════════════════════════
   GreenInfer Chat — Streaming Animation Additions
   
   HOW TO INTEGRATE:
   Add <script src="/chat-streaming.js"></script> at the end
   of chat.html, AFTER the main <script> block.
   
   This file:
   1. Patches mkAiMsg to use streaming text animation
   2. Adds a rich "thinking" bubble that replaces .typing-ind
   3. Connects sessions to the dashboard bridge on new chat
   4. Adds a "thinking status" that cycles through routing steps
══════════════════════════════════════════════════════════ */

/* Inject streaming CSS */
(function injectStyles() {
  const style = document.createElement('style');
  style.textContent = `
    @keyframes cursorBlink { 0%,100%{opacity:1} 49%{opacity:1} 50%{opacity:0} }

    .stream-cursor {
      display:inline-block;
      width:2px; height:1.1em;
      background:var(--green-core);
      margin-left:1px;
      vertical-align:text-bottom;
      animation:cursorBlink .9s infinite;
    }

    /* Enhanced thinking bubble */
    .thinking-bubble-wrap {
      display:flex; padding:3px 18px;
      animation:fadeUp .18s ease;
    }
    .thinking-bubble {
      display:flex; align-items:center; gap:10px;
      padding:11px 15px;
      background:var(--bg-surface);
      border:1px solid var(--border);
      border-radius:var(--radius-md);
      font-size:.8rem; font-family:var(--font-mono);
      position:relative; overflow:hidden;
    }
    .thinking-bubble::before {
      content:''; position:absolute; left:0; top:0; bottom:0;
      width:2px; background:var(--green-core);
      box-shadow:0 0 8px var(--green-core);
    }
    .think-icon { font-size:.85rem; flex-shrink:0; }
    .think-dots { display:flex; gap:3px; align-items:center; flex-shrink:0; }
    .think-dot {
      width:4px; height:4px; border-radius:50%;
      animation:blink 1.1s ease-in-out infinite;
    }
    .think-dot:nth-child(1) { background:var(--green-core); }
    .think-dot:nth-child(2) { background:var(--teal-accent); animation-delay:.18s; }
    .think-dot:nth-child(3) { background:var(--amber-warn); animation-delay:.36s; }
    .think-text {
      color:var(--text-muted); font-size:.7rem;
      transition:all .25s ease;
    }
    .think-step-trail {
      display:flex; gap:5px; align-items:center; flex-wrap:wrap;
    }
    .think-step {
      font-size:.63rem; padding:1px 6px;
      background:rgba(0,255,160,.06); border:1px solid rgba(0,255,160,.12);
      border-radius:99px; color:var(--green-core);
      opacity:0; transition:opacity .3s ease;
    }
    .think-step.done { opacity:1; }

    /* Message stream reveal */
    .msg-stream-wrap { min-height:1em; }

    /* Meta fade in */
    .inf-meta-anim {
      opacity:0; transform:translateY(4px);
      transition:opacity .35s ease, transform .35s ease;
    }
    .inf-meta-anim.show { opacity:1; transform:translateY(0); }

    /* Eff toggle fade in */
    .eff-toggle-anim {
      opacity:0; transform:translateY(4px);
      transition:opacity .35s ease .1s, transform .35s ease .1s;
    }
    .eff-toggle-anim.show { opacity:1; transform:translateY(0); }
  `;
  document.head.appendChild(style);
})();

/* ── THINKING STEPS SEQUENCE ── */
const THINK_STEPS = [
  { icon:'&#128300;', text:'Scoring complexity...' },
  { icon:'&#9889;',   text:'Running T5 optimizer...' },
  { icon:'&#127758;', text:'Checking ERCOT grid...' },
  { icon:'&#127919;', text:'Routing to model tier...' },
  { icon:'&#128161;', text:'Generating response...' },
];

/* ── THINKING BUBBLE ── */
function createThinkingBubble() {
  const w = document.createElement('div');
  w.className = 'thinking-bubble-wrap';
  w.id = 'thinking-bubble';
  w.innerHTML = `
    <div class="thinking-bubble">
      <span class="think-icon" id="think-icon">&#128300;</span>
      <div class="think-dots">
        <div class="think-dot"></div>
        <div class="think-dot"></div>
        <div class="think-dot"></div>
      </div>
      <span class="think-text" id="think-text">Analyzing query...</span>
      <div class="think-step-trail" id="think-trail"></div>
    </div>`;
  return w;
}

let thinkTimer = null;
function startThinkingAnimation() {
  const bubble = createThinkingBubble();
  const $msgs = document.getElementById('chat-msgs');
  if ($msgs) { $msgs.appendChild(bubble); scrollBot(); }

  let step = 0;
  const trail = document.getElementById('think-trail');
  const iconEl = document.getElementById('think-icon');
  const textEl = document.getElementById('think-text');

  function advance() {
    if (step >= THINK_STEPS.length) return;
    const s = THINK_STEPS[step];
    if (iconEl) iconEl.innerHTML = s.icon;
    if (textEl) {
      textEl.style.opacity = '0';
      setTimeout(() => { if(textEl){textEl.textContent=s.text.replace(/\.\.\./,''); textEl.style.opacity='1';} }, 150);
    }
    // Add step badge
    if (trail && step > 0) {
      const badge = document.createElement('span');
      badge.className = 'think-step';
      badge.innerHTML = THINK_STEPS[step-1].icon + ' ' + ['Scored','Optimized','Grid OK','Routing...'][step-1] || '';
      trail.appendChild(badge);
      setTimeout(() => badge.classList.add('done'), 50);
    }
    step++;
    thinkTimer = setTimeout(advance, 600 + Math.random()*400);
  }
  advance();
}

function stopThinkingAnimation() {
  clearTimeout(thinkTimer);
  const b = document.getElementById('thinking-bubble');
  if (b) {
    b.style.opacity = '0'; b.style.transform = 'translateY(-4px)';
    b.style.transition = 'all .2s ease';
    setTimeout(() => b.remove(), 200);
  }
}

/* ── STREAMING TEXT ── */
function streamTextInto(el, text, onDone) {
  el.innerHTML = '';
  const cursor = document.createElement('span');
  cursor.className = 'stream-cursor';
  const textNode = document.createElement('span');
  textNode.className = 'msg-stream-wrap';
  el.appendChild(textNode);
  el.appendChild(cursor);

  let i = 0;
  const charDelay = () => {
    const ch = text[i] || '';
    if (ch === '\n') return 10;
    if (ch === ' ') return 28;
    if (/[.,!?;:]/.test(ch)) return 55;
    if (ch === '`') return 8;
    return Math.random() * 16 + 5;
  };

  function next() {
    if (i < text.length) {
      i++;
      const partial = text.slice(0, i);
      // Lightweight partial markdown — just bold and inline code
      textNode.innerHTML = partial
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/```[\s\S]*?```|`[^`]+`/g, m => {
          if (m.startsWith('```')) return `<pre style="background:var(--bg-void);border:1px solid var(--border);border-radius:8px;padding:8px 10px;margin:6px 0;overflow-x:auto;font-size:.79rem">${m.slice(3,-3).replace(/^\w+\n/,'')}</pre>`;
          return `<code style="background:var(--bg-raised);padding:1px 5px;border-radius:3px;font-family:var(--font-mono);font-size:.8em">${m.slice(1,-1)}</code>`;
        })
        .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
        .replace(/\*(.+?)\*/g,'<em>$1</em>')
        .replace(/^### (.+)$/gm,'<strong>$1</strong>')
        .replace(/^## (.+)$/gm,'<strong style="font-size:1.05em">$1</strong>')
        .replace(/^# (.+)$/gm,'<strong style="font-size:1.1em">$1</strong>')
        .replace(/\n/g,'<br/>');

      setTimeout(next, charDelay());
    } else {
      // Done — swap to full rendered markdown
      cursor.remove();
      textNode.innerHTML = typeof renderMd === 'function' ? renderMd(text) : text;
      // Add copy buttons to code blocks
      textNode.querySelectorAll('pre code').forEach(block => {
        if (window.Prism) Prism.highlightElement(block);
        const pre = block.parentElement;
        if (pre.querySelector('.copy-btn')) return;
        pre.style.position = 'relative';
        const cb = document.createElement('button');
        cb.className = 'copy-btn'; cb.textContent = 'Copy';
        cb.onclick = () => navigator.clipboard.writeText(block.textContent).then(()=>{
          cb.textContent='Copied!'; setTimeout(()=>cb.textContent='Copy',1500);
        });
        pre.appendChild(cb);
      });
      if (onDone) onDone();
    }
  }
  setTimeout(next, 30);
}

/* ── PATCH mkAiMsg TO USE STREAMING ── */
(function patchMkAiMsg() {
  // Wait for DOM to be ready, then patch
  const orig_mkAiMsg = window.mkAiMsg;
  if (typeof orig_mkAiMsg !== 'function') {
    // Try again after a tick
    setTimeout(patchMkAiMsg, 50);
    return;
  }

  window.mkAiMsg = function(data, gs) {
    const w = orig_mkAiMsg(data, gs);
    // Find the msg-body element and stream into it
    const bodyEl = w.querySelector('.msg-body');
    if (bodyEl && data.response) {
      const fullText = data.response;
      bodyEl.innerHTML = ''; // Clear (orig_mkAiMsg already rendered)
      streamTextInto(bodyEl, fullText, () => {
        // Reveal meta tags with animation after stream
        const meta = w.querySelector('.inf-meta');
        const eff = w.querySelector('.eff-toggle');
        if (meta) { meta.classList.add('inf-meta-anim'); setTimeout(()=>meta.classList.add('show'),20); }
        if (eff) { eff.classList.add('eff-toggle-anim'); setTimeout(()=>eff.classList.add('show'),80); }
        scrollBot();
      });
    }
    return w;
  };
})();

/* ── PATCH send() TO USE RICH THINKING BUBBLE ── */
(function patchSend() {
  const origSend = window.send;
  if (typeof origSend !== 'function') {
    setTimeout(patchSend, 50);
    return;
  }

  window.send = async function(text, skipPrev=false, imgList=null) {
    // Start thinking animation
    const $typing = document.getElementById('typing-ind');
    if ($typing) $typing.classList.remove('show');
    startThinkingAnimation();

    // Patch typing-ind.classList.add('show') to update thinking bubble instead
    const origShow = HTMLElement.prototype.classList;
    
    // Override $tyTxt updates to update thinking bubble
    const tyTxt = document.getElementById('ty-txt');
    if (tyTxt) {
      const origTyObserver = new MutationObserver(() => {
        const textEl = document.getElementById('think-text');
        if (textEl && tyTxt.textContent) {
          textEl.textContent = tyTxt.textContent;
        }
      });
      origTyObserver.observe(tyTxt, { childList:true, characterData:true, subtree:true });
      setTimeout(() => origTyObserver.disconnect(), 30000);
    }

    // Intercept typing-ind show/hide
    const _origShow = document.getElementById('typing-ind');
    if (_origShow) {
      const _origClassList = _origShow.classList;
      const _add = _origClassList.add.bind(_origClassList);
      const _remove = _origClassList.remove.bind(_origClassList);
      _origClassList.add = function(...args) {
        if (args.includes('show')) {
          // Don't show old indicator, update new bubble
          const textEl = document.getElementById('think-text');
          if (textEl && tyTxt) textEl.textContent = tyTxt.textContent || 'Processing...';
          return;
        }
        _add(...args);
      };
      _origClassList.remove = function(...args) {
        if (args.includes('show')) {
          stopThinkingAnimation();
          // Restore
          _origClassList.add = _add;
          _origClassList.remove = _remove;
          return;
        }
        _remove(...args);
      };
    }

    return origSend.call(this, text, skipPrev, imgList);
  };
})();

/* ── PATCH newChat() TO SAVE SESSION TO DASHBOARD ── */
(function patchNewChat() {
  const origNewChat = window.newChat;
  if (typeof origNewChat !== 'function') {
    setTimeout(patchNewChat, 50);
    return;
  }

  window.newChat = function() {
    // Save current session to dashboard before clearing
    if (typeof S !== 'undefined' && S.prompts > 0 && window.GIDashboard) {
      const tierMap = { s:'small', m:'medium', l:'large' };
      const topEntry = Object.entries(S.models||{}).sort((a,b)=>b[1]-a[1])[0];
      const topTier = topEntry ? topEntry[0] : 's';
      const avgSaved = S.savedPctN > 0 ? Math.round(S.savedPctSum/S.savedPctN) : 0;
      window.GIDashboard.saveSession({
        title: S.chatTitle || 'Chat session',
        prompt_count: S.prompts,
        energy_mwh: Number((S.energy||0).toFixed(4)),
        co2_grams: Number((S.co2||0).toFixed(6)),
        tokens_saved: S.tokSaved || 0,
        avg_saved_pct: avgSaved,
        dominant_model: tierMap[topTier] || 'small',
        mode: S.mode || 'balanced',
        user_id: S.user?.id
      });
    }
    return origNewChat.call(this);
  };
})();

/* ── ADD DASHBOARD LINK TO NAV ── */
(function addDashNavLink() {
  const navLinks = document.querySelector('.nav-links');
  if (!navLinks) return;
  const dashLi = document.createElement('li');
  dashLi.innerHTML = '<a href="/dashboard">Dashboard</a>';
  navLinks.appendChild(dashLi);
  // Set active if on dashboard page
  const p = location.pathname;
  if (p.includes('dashboard')) dashLi.querySelector('a').classList.add('active');
})();

console.log('%c[GreenInfer] Streaming patch loaded ✓', 'color:#00ffa0;font-family:monospace');
