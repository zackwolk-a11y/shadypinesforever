/**
 * Phone controls (DOM), driving the same Controls as the keyboard so every menu works too.
 *  - Phone upright: the game sits on top, the controller fills the space below it.
 *  - Phone sideways: the game is scaled to the FULL screen height and the buttons move into the
 *    spare space at the left and right edges, so nothing covers the action.
 *  - First launch upright: a "turn your phone sideways" card.
 * All CSS lives here (injected), so every copy of the page — Vite build, single-file HTML,
 * artifact, Netlify upload — gets the same layout.
 */
import { Controls, Action } from './input';
import { toggleFullscreen } from './fullscreen';

const BUTTONS: { a: Action[]; label: string; cls: string }[] = [
  { a: ['up'], label: '▲', cls: 'up' }, { a: ['left'], label: '◀', cls: 'left' }, { a: ['right'], label: '▶', cls: 'right' }, { a: ['down'], label: '▼', cls: 'down' },
  { a: ['jump', 'confirm'], label: 'JUMP', cls: 'jump' }, { a: ['honk'], label: 'HONK', cls: 'honk' },
  { a: ['ability'], label: 'POWER', cls: 'power' }, { a: ['interact', 'confirm'], label: 'SIP', cls: 'sip' },
  { a: ['pause'], label: 'II', cls: 'pause' },
];
/** true when the DOM controller is showing (upright pad OR sideways side-bars) → hide in-canvas buttons */
export const portraitPad = () => document.body.classList.contains('pad-on') || document.body.classList.contains('side-on');

const CSS = `
  body.side-on #game { left: var(--bar) !important; right: var(--bar) !important; top: 0 !important; bottom: 0 !important; }
  .side { display: none; position: fixed; top: 0; bottom: 0; width: var(--bar); box-sizing: border-box; gap: 8px; background: #18131c;
    padding: max(8px, env(safe-area-inset-top)) 6px max(10px, env(safe-area-inset-bottom)) 6px; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  body.side-on .side { display: grid; }
  .side.l { left: 0; padding-left: max(6px, env(safe-area-inset-left)); grid-template-rows: 30px 1fr 1.3fr 1fr; grid-template-areas: "pause pause" "up up" "left right" "down down"; }
  .side.r { right: 0; padding-right: max(6px, env(safe-area-inset-right)); grid-template-rows: 30px 1fr 1fr 1fr 1.4fr; grid-template-areas: "fs fs" "honk honk" "power power" "sip sip" "jump jump"; }
  .side .pb { min-height: 0; min-width: 0; padding: 0; overflow: hidden; white-space: nowrap; font-size: 13px; border-radius: 12px; }
  .side .pb.jump { font-size: 17px; }
  .pb.fs { grid-area: fs; }
  #rotate { position: fixed; inset: 0; z-index: 50; display: none; flex-direction: column; align-items: center; justify-content: center; gap: 18px;
    background: rgba(24,19,28,0.96); color: #fff; font: bold 18px monospace; text-align: center; padding: 24px; }
  body.ask-rotate #rotate { display: flex; }
  #rotate .phone { width: 56px; height: 96px; border: 4px solid #fff; border-radius: 12px; position: relative; animation: rot 1.8s ease-in-out infinite; }
  #rotate .phone::after { content: ''; position: absolute; left: 50%; bottom: 6px; width: 12px; height: 4px; margin-left: -6px; background: #fff; border-radius: 2px; }
  #rotate .sub { font-size: 14px; color: #f0c040; }
  #rotate button { font: bold 14px monospace; color: #fff; background: #2a2430; border: 2px solid #46364f; border-radius: 12px; padding: 12px 18px; }
  @keyframes rot { 0%, 20% { transform: rotate(0deg); } 55%, 100% { transform: rotate(-90deg); } }
`;

export function installTouchpad(isTouch: () => boolean) {
  const pad = document.getElementById('pad');
  if (!pad) return;
  const style = document.createElement('style'); style.textContent = CSS; document.head.appendChild(style);
  const sideL = document.createElement('div'); sideL.className = 'side l';
  const sideR = document.createElement('div'); sideR.className = 'side r';
  document.body.append(sideL, sideR);
  const els: Record<string, HTMLButtonElement> = {};
  for (const b of BUTTONS) {
    const el = document.createElement('button');
    el.className = 'pb ' + b.cls; el.textContent = b.label; el.type = 'button';
    const set = (v: boolean) => { for (const a of b.a) Controls.setTouch(a, v); el.classList.toggle('on', v); };
    el.addEventListener('pointerdown', (e) => { e.preventDefault(); try { el.setPointerCapture?.(e.pointerId); } catch { /* not capturable */ } set(true); });
    for (const ev of ['pointerup', 'pointercancel', 'lostpointercapture']) el.addEventListener(ev, () => set(false));
    el.addEventListener('contextmenu', (e) => e.preventDefault());
    pad.appendChild(el); els[b.cls] = el;
  }
  // fullscreen button; triggered on click (pointer up) so it counts as a user gesture
  const fs = document.createElement('button');
  fs.className = 'pb pause fs'; fs.type = 'button'; fs.textContent = '⛶ FULL';
  fs.title = 'Full screen';
  fs.addEventListener('click', (e) => { e.preventDefault(); void toggleFullscreen(); });
  pad.appendChild(fs);

  // "turn your phone sideways" card (shown once at the start when the phone is upright)
  const rot = document.createElement('div'); rot.id = 'rotate';
  rot.innerHTML = '<div class="phone"></div><div>TURN YOUR PHONE SIDEWAYS</div><div class="sub">THE GOOSE PLAYS BEST FULL SCREEN, HORIZONTAL</div>';
  const keep = document.createElement('button'); keep.type = 'button'; keep.textContent = 'PLAY UPRIGHT INSTEAD';
  let rotateDismissed = false;
  keep.addEventListener('click', () => { rotateDismissed = true; document.body.classList.remove('ask-rotate'); });
  rot.appendChild(keep); document.body.appendChild(rot);

  // measure the notch / home-bar insets (CSS env() values) once per layout
  const probe = document.createElement('div');
  probe.style.cssText = 'position:fixed;visibility:hidden;pointer-events:none;padding-left:env(safe-area-inset-left);padding-right:env(safe-area-inset-right)';
  document.body.appendChild(probe);

  let mode = '';
  const place = (m: string) => {
    if (m === mode) return; mode = m;
    if (m === 'side') {
      for (const k of ['pause', 'up', 'left', 'right', 'down']) sideL.appendChild(els[k]);
      for (const k of ['honk', 'power', 'sip', 'jump']) sideR.appendChild(els[k]);
      sideR.insertBefore(fs, sideR.firstChild); fs.style.gridArea = 'fs';
    } else {
      for (const k of Object.keys(els)) pad.appendChild(els[k]);
      pad.appendChild(fs); fs.style.gridArea = '1 / 5 / 2 / 7';
    }
  };
  const update = () => {
    const touch = isTouch();
    const W = window.innerWidth, H = window.innerHeight;
    const portrait = H > W;
    const cs = getComputedStyle(probe);
    const insets = (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0);
    // sideways: game at full height; whatever width is left over becomes the two button columns
    const bar = Math.floor((W - insets - (H * 16) / 9) / 2 + Math.max(parseFloat(cs.paddingLeft) || 0, parseFloat(cs.paddingRight) || 0));
    const side = false && bar >= 64; // sideways: original in-game buttons; the game itself widens to fill the screen (see view.ts)
    document.body.classList.toggle('pad-on', portrait && touch);
    document.body.classList.toggle('side-on', side);
    document.body.classList.toggle('ask-rotate', portrait && touch && !rotateDismissed);
    if (!portrait) rotateDismissed = true; // once they've turned it, never nag again this session
    document.body.style.setProperty('--bar', side ? bar + 'px' : '0px');
    place(side ? 'side' : 'pad');
    window.dispatchEvent(new Event('resize-game'));
  };
  window.addEventListener('resize', update); window.addEventListener('orientationchange', update);
  update();
  setInterval(update, 1000);
}
