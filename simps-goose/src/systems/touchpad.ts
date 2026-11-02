/**
 * Portrait phone controller (DOM, below the game). Drives the same Controls as the
 * keyboard, so every menu works with the d-pad + JUMP/SIP. Landscape uses the in-game buttons.
 */
import { Controls, Action } from './input';
import { toggleFullscreen } from './fullscreen';

const BUTTONS: { a: Action[]; label: string; cls: string }[] = [
  { a: ['up'], label: '▲', cls: 'up' }, { a: ['left'], label: '◀', cls: 'left' }, { a: ['right'], label: '▶', cls: 'right' }, { a: ['down'], label: '▼', cls: 'down' },
  { a: ['jump', 'confirm'], label: 'JUMP', cls: 'jump' }, { a: ['honk'], label: 'HONK', cls: 'honk' },
  { a: ['ability'], label: 'POWER', cls: 'power' }, { a: ['interact', 'confirm'], label: 'SIP', cls: 'sip' },
  { a: ['pause'], label: 'II', cls: 'pause' },
];
export const portraitPad = () => document.body.classList.contains('pad-on');

export function installTouchpad(isTouch: () => boolean) {
  const pad = document.getElementById('pad');
  if (!pad) return;
  for (const b of BUTTONS) {
    const el = document.createElement('button');
    el.className = 'pb ' + b.cls; el.textContent = b.label; el.type = 'button';
    const set = (v: boolean) => { for (const a of b.a) Controls.setTouch(a, v); el.classList.toggle('on', v); };
    el.addEventListener('pointerdown', (e) => { e.preventDefault(); try { el.setPointerCapture?.(e.pointerId); } catch { /* not capturable */ } set(true); });
    for (const ev of ['pointerup', 'pointercancel', 'lostpointercapture']) el.addEventListener(ev, () => set(false));
    el.addEventListener('contextmenu', (e) => e.preventDefault());
    pad.appendChild(el);
  }
  // fullscreen button (top-right of the pad); triggered on pointerup so it counts as a user gesture
  const fs = document.createElement('button');
  fs.className = 'pb pause fs'; fs.type = 'button'; fs.textContent = '⛶ FULL';
  fs.style.gridArea = '1 / 5 / 2 / 7';
  fs.addEventListener('click', (e) => { e.preventDefault(); void toggleFullscreen(); });
  pad.appendChild(fs);
  const update = () => {
    const portrait = window.innerHeight > window.innerWidth;
    document.body.classList.toggle('pad-on', portrait && isTouch());
    window.dispatchEvent(new Event('resize-game'));
  };
  window.addEventListener('resize', update); window.addEventListener('orientationchange', update);
  update();
  setInterval(update, 1000);
}
