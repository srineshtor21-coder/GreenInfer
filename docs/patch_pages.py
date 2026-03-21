"""
Run this script from your GreenInfer/docs/ folder to patch all HTML pages:
  1. Remove the "Live" badge from nav
  2. Add light/dark mode toggle button
  3. Add light mode CSS
  4. Set the real BACKEND_URL in chat.html
  5. Add light mode JS to all pages

Usage:
  cd C:\\Users\\srine\\OneDrive\\Documents\\GitHub\\GreenInfer\\docs
  python patch_pages.py
"""

import os
import re

BACKEND_URL = "https://sirenice-greeninfer-backend.hf.space"

LIGHT_MODE_CSS = """
body.light {
  --bg-void: #f0f7f4;
  --bg-deep: #e4f0eb;
  --bg-surface: #d8ece3;
  --bg-raised: #cce4d8;
  --bg-card: #c0dccb;
  --border: rgba(0, 120, 80, 0.12);
  --border-mid: rgba(0, 120, 80, 0.22);
  --text-primary: #0a1f18;
  --text-secondary: #2a5a45;
  --text-muted: #4a8a6a;
  --text-dim: #7ab89a;
}
body.light .nav {
  background: rgba(240, 247, 244, 0.92);
}
.theme-toggle {
  background: none;
  border: 1px solid var(--border-mid);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 6px 10px;
  border-radius: var(--radius-md);
  font-size: 0.85rem;
  transition: all 0.15s;
  font-family: var(--font-body);
}
.theme-toggle:hover {
  border-color: var(--green-core);
  color: var(--green-core);
}
"""

THEME_JS = """
function initTheme() {
  const btn = document.getElementById('theme-btn');
  if (!btn) return;
  const saved = localStorage.getItem('gi-theme');
  if (saved === 'light') {
    document.body.classList.add('light');
    btn.textContent = '🌙 Dark';
  }
  btn.addEventListener('click', () => {
    document.body.classList.toggle('light');
    const isLight = document.body.classList.contains('light');
    localStorage.setItem('gi-theme', isLight ? 'light' : 'dark');
    btn.textContent = isLight ? '🌙 Dark' : '☀️ Light';
  });
}
"""

pages = [f for f in os.listdir('.') if f.endswith('.html')]
print(f"Found {len(pages)} HTML files to patch")

for page in pages:
    with open(page, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # 1. Remove the standalone Live badge from nav
    content = re.sub(r'\s*<span class="live-badge">Live</span>\s*', ' ', content)
    content = re.sub(r'\s*<span class="live-badge">Live Data</span>\s*', ' ', content)

    # 2. Add light mode CSS before </style> in first style block
    if 'body.light' not in content and LIGHT_MODE_CSS.strip() not in content:
        content = content.replace('</style>\n  <style>', f'{LIGHT_MODE_CSS}\n</style>\n  <style>', 1)
        # fallback if single style block
        if 'body.light' not in content:
            content = content.replace('body::before {', f'{LIGHT_MODE_CSS}\nbody::before {{', 1)

    # 3. Add theme toggle button to nav-actions (before Launch Chat or Docs button)
    if 'theme-toggle' not in content:
        content = content.replace(
            '<div class="nav-actions">',
            '<div class="nav-actions">\n      <button class="theme-toggle" id="theme-btn" aria-label="Toggle light mode">&#9728;&#65039; Light</button>'
        )

    # 4. Add initTheme to DOMContentLoaded
    if 'initTheme' not in content:
        content = content.replace(
            "document.addEventListener('DOMContentLoaded', () => {",
            f"{THEME_JS}\ndocument.addEventListener('DOMContentLoaded', () => {{"
        )
        # Also call it
        content = content.replace(
            'initTooltips();\n});',
            'initTooltips();\n  initTheme();\n});'
        )
        content = content.replace(
            'initCounters();\n});',
            'initCounters();\n  initTheme();\n});'
        )

    # 5. Set real BACKEND_URL in chat.html
    if page == 'chat.html':
        content = re.sub(
            r'const BACKEND_URL\s*=\s*"[^"]*"',
            f'const BACKEND_URL = "{BACKEND_URL}"',
            content
        )
        print(f"  -> Set BACKEND_URL to {BACKEND_URL}")

    if content != original:
        with open(page, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  Patched: {page}")
    else:
        print(f"  No changes: {page}")

print("\nDone. Commit and push to GitHub to deploy changes.")
