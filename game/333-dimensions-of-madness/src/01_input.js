// ============================================================================
// Input: keyboard, gamepad, touchscreen -> unified actions
// ============================================================================
const ACTIONS = ['left', 'right', 'up', 'down', 'jump', 'whip', 'spit', 'bash', 'dash', 'scream', 'grapple', 'headbang', 'transform', 'summon', 'pause', 'confirm', 'back'];
const KEYMAP = { // three buttons: MOVE, JUMP, ATTACK (+ pause). 'whip' is the internal name of ATTACK.
  ArrowLeft: 'left', KeyA: 'left', ArrowRight: 'right', KeyD: 'right', ArrowUp: 'up', KeyW: 'up', ArrowDown: 'down', KeyS: 'down',
  Space: 'jump', KeyZ: 'jump', KeyK: 'jump', KeyX: 'whip', KeyJ: 'whip', KeyC: 'whip', ShiftLeft: 'whip', ShiftRight: 'whip', KeyL: 'whip',
  Escape: 'pause', KeyP: 'pause', Enter: 'confirm', Backspace: 'back'
};
const Input = {
  held: {}, pressed: {}, released: {}, _down: {}, _prev: {}, _latch: {}, mode: 'keys', touchOn: false, anyPressed: false,
  update() {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    const pad = [...pads].find(p => p && p.connected);
    const now = Object.assign({}, this._down);
    if (pad) {
      const b = i => pad.buttons[i] && pad.buttons[i].pressed, ax = pad.axes[0] || 0, ay = pad.axes[1] || 0;
      const map = { left: b(14) || ax < -.4, right: b(15) || ax > .4, up: b(12) || ay < -.5, down: b(13) || ay > .5,
        jump: b(0), whip: b(2) || b(1) || b(3) || b(5) || b(7), pause: b(9) };
      for (const k in map) if (map[k]) { now[k] = true; this.mode = 'pad'; }
      if (map.jump) now.confirm = true;
      if (b(1)) now.back = true;
    }
    if (now.jump) now.confirm = true;
    this.anyPressed = false;
    for (const a of ACTIONS) {
      const d = !!now[a];
      this.pressed[a] = (d && !this._prev[a]) || !!this._latch[a]; this._latch[a] = false;
      this.released[a] = !d && this._prev[a];
      this.held[a] = d;
      if (this.pressed[a]) this.anyPressed = true;
      this._prev[a] = d;
    }
  },
  clear() { for (const a of ACTIONS) { this.pressed[a] = false; } }
};
window.addEventListener('keydown', e => {
  const a = KEYMAP[e.code]; if (a) { if (!Input._down[a]) Input._latch[a] = true; Input._down[a] = true; e.preventDefault(); Input.mode = 'keys'; }
  if (e.code === 'Escape') Input._down.back = true;
  if (e.code === 'F3') G.debug = !G.debug;
  AudioSys.unlock();
});
window.addEventListener('keyup', e => { const a = KEYMAP[e.code]; if (a) Input._down[a] = false; if (e.code === 'Escape') Input._down.back = false; });
window.addEventListener('blur', () => { Input._down = {}; });

// ---------------------------------------------------------------- touch controls
const Touch = {
  buttons: [['jump', 'JUMP', -68, -62, 92], ['whip', 'ATTACK', -172, -44, 80], ['pause', 'II', -36, 'top', 34]],
  init() {
    const root = document.getElementById('touch');
    for (const [act, label, rx, ry, size] of this.buttons) {
      const el = document.createElement('div'); el.className = 'tb'; el.dataset.a = act; el.textContent = label;
      el.style.width = el.style.height = size + 'px';
      el.style.right = (-rx - size / 2) + 'px';
      if (ry === 'top') el.style.top = '10px'; else el.style.bottom = (-ry - size / 2) + 'px';
      const on = e => { e.preventDefault(); Input._latch[act] = true; Input._down[act] = true; el.classList.add('down'); AudioSys.unlock(); if (act === 'jump') Input._down.confirm = true; if (act === 'pause') Input._down.back = true; };
      const off = e => { e.preventDefault(); Input._down[act] = false; el.classList.remove('down'); if (act === 'jump') Input._down.confirm = false; if (act === 'pause') Input._down.back = false; };
      el.addEventListener('touchstart', on, { passive: false }); el.addEventListener('touchend', off, { passive: false }); el.addEventListener('touchcancel', off, { passive: false });
      root.appendChild(el);
    }
    const stick = document.getElementById('stick'), knob = document.getElementById('knob');
    let sid = null;
    const move = t => {
      const r = stick.getBoundingClientRect(); const dx = t.clientX - (r.left + r.width / 2), dy = t.clientY - (r.top + r.height / 2);
      const m = Math.min(1, Math.hypot(dx, dy) / 50), an = Math.atan2(dy, dx);
      knob.style.left = (40 + Math.cos(an) * m * 40) + 'px'; knob.style.top = (40 + Math.sin(an) * m * 40) + 'px';
      Input._down.left = dx < -18; Input._down.right = dx > 18; Input._down.up = dy < -24; Input._down.down = dy > 24;
    };
    stick.addEventListener('touchstart', e => { e.preventDefault(); sid = e.changedTouches[0].identifier; move(e.changedTouches[0]); AudioSys.unlock(); }, { passive: false });
    stick.addEventListener('touchmove', e => { e.preventDefault(); for (const t of e.changedTouches) if (t.identifier === sid) move(t); }, { passive: false });
    const end = e => { for (const t of e.changedTouches) if (t.identifier === sid) { sid = null; knob.style.left = knob.style.top = '40px'; Input._down.left = Input._down.right = Input._down.up = Input._down.down = false; } };
    stick.addEventListener('touchend', end); stick.addEventListener('touchcancel', end);
    // tap on the game screen = confirm (menus / dialogue)
    canvas.addEventListener('touchstart', e => { e.preventDefault(); AudioSys.unlock(); Input._down.confirm = true; setTimeout(() => Input._down.confirm = false, 80); this.enable(); }, { passive: false });
    window.addEventListener('touchstart', () => this.enable(), { once: true });
  },
  enable() { if (!this.on) { this.on = true; Input.touchOn = true; document.getElementById('touch').classList.add('on'); Input.mode = 'touch'; } },
};
canvas.addEventListener('mousedown', () => AudioSys.unlock());
