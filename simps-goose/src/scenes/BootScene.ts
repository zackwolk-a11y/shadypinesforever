/** Boot: generate all pixel-art textures (cached), then hand off. */
import Phaser from 'phaser';
import { generateAll } from '../art/registry';
import { C } from '../art/palette';
import { settings } from '../systems/settings';
import { GS } from '../systems/gamestate';

export class BootScene extends Phaser.Scene {
  constructor() { super('Boot'); }
  create() {
    const g = this.add.graphics();
    g.fillStyle(C.blk2).fillRect(0, 0, 480, 270);
    g.fillStyle(C.red1).fillRect(190, 132, 100, 6);
    this.add.text(240, 118, 'POURING...', { fontFamily: 'monospace', fontSize: '10px', color: '#ffffff' }).setOrigin(0.5);
    const q = new URLSearchParams(location.search);
    const s = settings();
    const touch = q.get('touch') === '1' || (q.get('touch') !== '0' && s.touch !== 'off' && (s.touch === 'on' || 'ontouchstart' in window || navigator.maxTouchPoints > 0));
    this.registry.set('touch', touch);
    // let the loader frame render, then generate synchronously
    this.time.delayedCall(30, () => {
      const t0 = performance.now();
      generateAll(this);
      (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.genMs = Math.round(performance.now() - t0);
      this.scene.launch('Input');
      GS.newRun(q.get('mode') === 'demo' ? 'demo' : 'story');
      const start = q.get('scene');
      const MAP: Record<string, string> = { store: 'Store', intro: 'Intro', lab: 'Lab', dimension: 'Dimension', carb: 'BossCarb', fake: 'FakeEnd', cafe: 'Cafe', waterfront: 'Waterfront', ogopogo: 'Ogopogo', trueend: 'TrueEnd', journal: 'Journal' };
      if (q.get('burp')) GS.coffee = q.get('burp');
      if (q.get('skipintro')) this.registry.set('skipIntro', true);
      const key = (start && MAP[start]) || 'Title';
      if (this.scene.get(key)) this.scene.start(key); else this.scene.start('Title');
    });
  }
}

/** Persistent scene that owns the keyboard and polls controls first every frame. */
import { Controls } from '../systems/input';
import { saveSettings } from '../systems/settings';
export class InputScene extends Phaser.Scene {
  m!: Phaser.Input.Keyboard.Key;
  constructor() { super('Input'); }
  create() {
    Controls.bind(this);
    this.m = this.input.keyboard!.addKey('M');
  }
  update() {
    Controls.poll();
    if (Phaser.Input.Keyboard.JustDown(this.m)) saveSettings({ muted: !settings().muted });
  }
}
