/**
 * Installable app (PWA): offline service worker + an install hint.
 *  - iPhone/iPad Safari: a small banner "Share → Add to Home Screen" (that's the only way iOS gives a
 *    web game true full screen). Dismissable; never shown once running from the home screen.
 *  - Android/Chrome: an INSTALL button using the browser's own install prompt.
 * Only on a real website (https, top-level) — never inside the Claude artifact viewer or the dev server.
 */
const ss = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };
const set = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } };

export const isInstalled = () => (navigator as Navigator & { standalone?: boolean }).standalone === true
  || matchMedia('(display-mode: standalone)').matches || matchMedia('(display-mode: fullscreen)').matches;

export function installPwa() {
  const topLevel = (() => { try { return window.top === window; } catch { return false; } })();
  const force = new URLSearchParams(location.search).has('pwa'); // test switch for local servers
  if (!topLevel || (location.protocol !== 'https:' && !force)) return;
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(() => undefined);
  if (isInstalled() || ss('goose-install-hint') === 'off') return;

  const css = document.createElement('style');
  css.textContent = `#install { position: fixed; z-index: 60; left: 50%; bottom: max(10px, env(safe-area-inset-bottom)); transform: translateX(-50%);
    display: flex; align-items: center; gap: 10px; max-width: calc(100vw - 24px); box-sizing: border-box; padding: 9px 12px; border-radius: 14px;
    background: rgba(24,19,28,0.95); border: 2px solid #e02a3c; color: #fff; font: bold 13px monospace; }
    #install button { font: bold 13px monospace; color: #fff; background: #e02a3c; border: 0; border-radius: 10px; padding: 7px 11px; }
    #install .x { background: transparent; color: #aaa; padding: 4px 6px; }
    #install svg { flex: none; }`;
  document.head.appendChild(css);
  const bar = document.createElement('div'); bar.id = 'install';
  const close = () => { bar.remove(); set('goose-install-hint', 'off'); };
  const addX = () => { const x = document.createElement('button'); x.className = 'x'; x.textContent = '✕'; x.setAttribute('aria-label', 'Close'); x.onclick = close; bar.appendChild(x); };
  const ios = /iP(hone|od|ad)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  if (ios) {
    // the iOS "share" glyph: a box with an arrow up
    bar.innerHTML = `<svg width="18" height="22" viewBox="0 0 18 22" fill="none" stroke="#fff" stroke-width="2"><path d="M9 14V2M4 6l5-5 5 5"/><path d="M6 9H2v12h14V9h-4"/></svg>
      <span>FULL SCREEN: TAP SHARE, THEN <b>ADD TO HOME SCREEN</b></span>`;
  } else {
    let prompt: (Event & { prompt: () => void }) | null = null;
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault(); prompt = e as Event & { prompt: () => void };
      bar.innerHTML = '<span>PLAY FULL SCREEN AS AN APP</span>';
      const b = document.createElement('button'); b.textContent = 'INSTALL'; b.onclick = () => { prompt?.prompt(); close(); };
      bar.appendChild(b); addX(); document.body.appendChild(bar);
    });
    return;
  }
  addX();
  document.body.appendChild(bar);
  setTimeout(() => bar.remove(), 20000); // out of the way once play starts
}
