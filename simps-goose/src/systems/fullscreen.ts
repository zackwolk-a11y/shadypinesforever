/**
 * Fullscreen toggle (F key, the FS button in the HUD/title, and the ⛶ button on the phone pad).
 * Fullscreens the whole page so the portrait controller stays visible. Where the browser or an
 * embedding frame refuses (e.g. iPhone Safari, sandboxed iframes) we say so instead of failing silently.
 */
type FsDoc = Document & { webkitFullscreenElement?: Element; webkitExitFullscreen?: () => Promise<void> | void };
type FsEl = HTMLElement & { webkitRequestFullscreen?: () => Promise<void> | void };

let notify: (msg: string, sub?: string) => void = () => undefined;
export const setFullscreenNotifier = (f: typeof notify) => { notify = f; };

export const isFullscreen = () => { const d = document as FsDoc; return !!(d.fullscreenElement || d.webkitFullscreenElement); };
export const fullscreenSupported = () => { const el = document.documentElement as FsEl; const d = document as Document & { webkitFullscreenEnabled?: boolean }; return !!((typeof el.requestFullscreen === 'function' || typeof el.webkitRequestFullscreen === 'function') && (document.fullscreenEnabled ?? d.webkitFullscreenEnabled ?? true)); };

export async function toggleFullscreen() {
  const d = document as FsDoc;
  try {
    if (isFullscreen()) { await (typeof d.exitFullscreen === 'function' ? d.exitFullscreen() : d.webkitExitFullscreen?.()); return; }
    if (!fullscreenSupported()) throw new Error('unsupported');
    const el = document.documentElement as FsEl;
    await (typeof el.requestFullscreen === 'function' ? el.requestFullscreen({ navigationUI: 'hide' }) : el.webkitRequestFullscreen?.());
    // landscape is nicer on phones when the browser allows locking it (ignored elsewhere)
    try { await (screen.orientation as ScreenOrientation & { lock?: (o: string) => Promise<void> }).lock?.('landscape'); } catch { /* not allowed */ }
  } catch {
    notify('FULLSCREEN NOT AVAILABLE HERE', 'OPEN THE GAME IN ITS OWN BROWSER TAB, OR ADD IT TO YOUR HOME SCREEN');
  }
}
