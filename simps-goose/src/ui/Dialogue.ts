/**
 * Dialogue box with portraits, typewriter text and talking animations.
 * JUMP / SIP / tap advances, ESC skips the whole conversation (an essential instruction,
 * if any, is still shown as a toast so skipping never hides how to play).
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { txt } from '../art/font';
import { Controls } from '../systems/input';
import { SFX } from '../audio/sfx';
import type { Person } from '../entities/Person';

export type Line = [speaker: string, text: string, anim?: string];
const NAMES: Record<string, string> = { dave: 'DAVE', gerry: 'GERRY', goose: 'THE GOOSE', sam: 'SAM', barista: 'BARISTA' };
const PORTRAIT: Record<string, string> = { dave: 'portrait_dave', gerry: 'portrait_gerry' };

export class Dialogue {
  c: Phaser.GameObjects.Container; text: Phaser.GameObjects.BitmapText; name: Phaser.GameObjects.BitmapText; portrait: Phaser.GameObjects.Image; gooseFace: Phaser.GameObjects.Sprite; hint: Phaser.GameObjects.BitmapText;
  i = 0; shown = 0; t = 0; done = false; tapped = false;
  constructor(public scene: Phaser.Scene, public lines: Line[], public actors: Record<string, Person | undefined>, public onDone: (skipped?: boolean) => void, public skipNote?: [string, string]) {
    const s = scene;
    this.c = s.add.container(0, 0).setScrollFactor(0).setDepth(200);
    const g = s.add.graphics();
    g.fillStyle(C.ink, 0.92).fillRoundedRect(10, 68, 460, 68, 6).lineStyle(2, C.red1).strokeRoundedRect(11, 69, 458, 66, 6);
    g.fillStyle(C.blk2).fillRoundedRect(14, 56, 66, 78, 5).lineStyle(2, C.red1).strokeRoundedRect(14, 56, 66, 78, 5);
    this.portrait = s.add.image(47, 95, 'portrait_dave');
    this.gooseFace = s.add.sprite(47, 122, 'goose', 'front_0').setOrigin(22 / 48, 46 / 48).setScale(1.6).play('g_front');
    const plate = s.add.graphics().fillStyle(C.red1).fillRoundedRect(88, 62, 90, 13, 3);
    this.name = txt(s, 133, 64, '', { align: 'center', outline: false, color: C.wht });
    this.text = txt(s, 90, 82, '', { outline: false, color: C.wht }).setMaxWidth(370);
    this.hint = txt(s, 462, 124, 'JUMP/TAP: NEXT  ESC: SKIP', { align: 'right', outline: false, color: C.st2 });
    s.add.image(458, 66, 'leaf9');
    this.c.add([g, this.portrait, this.gooseFace, plate, this.name, this.text, this.hint, s.add.image(458, 77, 'trident13').setScale(0.7)]);
    const zone = s.add.zone(0, 0, 480, 270).setOrigin(0).setScrollFactor(0).setDepth(199).setInteractive().on('pointerdown', () => { this.tapped = true; });
    this.c.setData('zone', zone);
    Controls.consumeAll();
    this.show();
  }
  show() {
    const [sp, , anim] = this.lines[this.i];
    this.name.setText(NAMES[sp] ?? sp.toUpperCase());
    const tex = PORTRAIT[sp];
    this.portrait.setVisible(!!tex); if (tex) this.portrait.setTexture(tex);
    this.gooseFace.setVisible(sp === 'goose');
    this.shown = 0; this.t = 0;
    for (const [k, a] of Object.entries(this.actors)) if (a) { if (k === sp) a.act(anim ?? 'talk', 99); else if (a.state !== 'cheer') a.act('idle', 99); }
    if (sp === 'goose') SFX.honk(1); else SFX.ui('move');
  }
  update(dt: number) {
    if (this.done) return;
    const full = this.lines[this.i][1];
    this.t += dt;
    const was = this.shown;
    this.shown = Math.min(full.length, Math.floor(this.t * 55));
    if (this.shown !== was && this.shown % 4 === 0 && this.lines[this.i][0] !== 'goose') SFX.ui('move');
    this.text.setText(full.slice(0, this.shown));
    const adv = Controls.pressed('jump') || Controls.pressed('interact') || Controls.pressed('confirm') || this.tapped;
    this.tapped = false;
    if (Controls.pressed('back') || Controls.pressed('pause')) return this.finish(true);
    if (adv) {
      if (this.shown < full.length) { this.t = 999; return; }
      this.i++;
      if (this.i >= this.lines.length) return this.finish(false);
      this.show();
    }
  }
  finish(skipped: boolean) {
    if (this.done) return;
    this.done = true;
    (this.c.getData('zone') as Phaser.GameObjects.Zone).destroy();
    this.c.destroy();
    for (const a of Object.values(this.actors)) if (a && a.state !== 'cheer') a.act('idle', 0.1);
    Controls.consumeAll();
    if (skipped && this.skipNote) this.scene.game.events.emit('hud:toast', this.skipNote[0], C.gold1, this.skipNote[1]);
    this.onDone(skipped);
  }
}
