/**
 * Unified controls: keyboard + on-screen touch buttons + gamepad.
 * Gameplay code only reads `Controls.down(a)` / `Controls.pressed(a)`.
 */
import Phaser from 'phaser';

export type Action = 'left' | 'right' | 'up' | 'down' | 'jump' | 'honk' | 'ability' | 'interact' | 'pause' | 'confirm' | 'back';
const KEYMAP: Record<Action, string[]> = {
  left: ['LEFT', 'A'], right: ['RIGHT', 'D'], up: ['UP', 'W'], down: ['DOWN', 'S'],
  jump: ['SPACE', 'Z'], honk: ['X'], ability: ['C'], interact: ['E'], pause: ['ESC', 'P'],
  confirm: ['ENTER', 'SPACE', 'E'], back: ['ESC', 'BACKSPACE'],
};

class ControlsImpl {
  private keys: Partial<Record<Action, Phaser.Input.Keyboard.Key[]>> = {};
  private prev: Partial<Record<Action, boolean>> = {};
  private cur: Partial<Record<Action, boolean>> = {};
  touch: Partial<Record<Action, boolean>> = {};
  /** taps latched between polls so a press+release inside one frame is never lost */
  private latch: Partial<Record<Action, boolean>> = {};
  private touchLatch: Partial<Record<Action, boolean>> = {};
  private scene: Phaser.Scene | null = null;
  usingTouch = false;
  anyPressed = false;

  bind(scene: Phaser.Scene) {
    if (this.scene === scene) return;
    this.scene = scene;
    const kb = scene.input.keyboard!;
    for (const a of Object.keys(KEYMAP) as Action[]) {
      this.keys[a] = KEYMAP[a].map((k) => kb.addKey(k, true, false));
      for (const key of this.keys[a]!) key.on('down', () => { this.latch[a] = true; });
    }
    kb.on('keydown', () => { this.usingTouch = false; });
  }
  /** Call exactly once per frame (from the persistent Input scene). */
  poll() {
    this.prev = this.cur;
    const n: Partial<Record<Action, boolean>> = {};
    const pads = typeof navigator !== 'undefined' && navigator.getGamepads ? navigator.getGamepads() : [];
    const pad = pads && Array.from(pads).find((p) => p && p.connected);
    for (const a of Object.keys(KEYMAP) as Action[]) {
      let v = !!this.keys[a]?.some((k) => k.isDown) || !!this.touch[a] || !!this.latch[a] || !!this.touchLatch[a];
      if (pad) {
        const ax = pad.axes[0] ?? 0, ay = pad.axes[1] ?? 0, b = (i: number) => !!pad.buttons[i]?.pressed;
        if (a === 'left') v ||= ax < -0.4 || b(14);
        if (a === 'right') v ||= ax > 0.4 || b(15);
        if (a === 'up') v ||= ay < -0.5 || b(12);
        if (a === 'down') v ||= ay > 0.5 || b(13);
        if (a === 'jump' || a === 'confirm') v ||= b(0);
        if (a === 'honk') v ||= b(2);
        if (a === 'ability') v ||= b(1) || b(5);
        if (a === 'interact') v ||= b(3);
        if (a === 'pause') v ||= b(9);
        if (a === 'back') v ||= b(1) && false;
      }
      n[a] = v;
    }
    this.cur = n;
    this.latch = {}; this.touchLatch = {};
    this.anyPressed = (Object.keys(n) as Action[]).some((a) => n[a] && !this.prev[a]);
  }
  down(a: Action) { return !!this.cur[a]; }
  pressed(a: Action) { return !!this.cur[a] && !this.prev[a]; }
  released(a: Action) { return !this.cur[a] && !!this.prev[a]; }
  /** Let the game "eat" a press so it isn't seen twice (e.g. menu → gameplay). */
  consume(a: Action) { this.prev[a] = true; }
  consumeAll() { for (const a of Object.keys(KEYMAP) as Action[]) this.prev[a] = !!this.cur[a]; this.anyPressed = false; }
  clearTouch() { this.touch = {}; }
  setTouch(a: Action, v: boolean) { if (v && !this.touch[a]) this.touchLatch[a] = true; this.touch[a] = v; }
}
export const Controls = new ControlsImpl();
