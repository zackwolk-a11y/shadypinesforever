/** Customers & staff with simple reactive AI. */
import Phaser from 'phaser';
import { emote } from './Emote';
import { SFX } from '../audio/sfx';

type PState = 'browse' | 'walk' | 'react' | 'flee' | 'laugh' | 'gesture' | 'cheer' | 'idle';
const REACTIONS = {
  honk: [['!', 'shock'], ['A GOOSE?!', 'shock'], ['HA HA!', 'laugh'], ['EEK!', 'flee'], ['HONK?', 'laugh'], ['WHOA!', 'shock']],
  bump: [['HEY!', 'shock'], ['OOF!', 'shock'], ['HA!', 'laugh']],
} as const;

export class Person {
  scene: Phaser.Scene;
  key: string;
  sprite: Phaser.GameObjects.Sprite;
  state: PState = 'browse';
  t = 0;
  home: number; range: [number, number];
  staff: boolean;
  target: number;
  facing = 1;
  cooldown = 0;
  pitch: number;
  reactIdx = 0;
  speed = 26;
  lastLine = 0;
  constructor(scene: Phaser.Scene, key: string, x: number, y: number, opts: { range?: [number, number]; staff?: boolean; facing?: number; depth?: number; state?: PState } = {}) {
    this.scene = scene; this.key = key;
    this.home = x; this.range = opts.range ?? [x - 60, x + 60];
    this.staff = !!opts.staff; this.target = x;
    this.pitch = 0.85 + (key.charCodeAt(key.length - 1) % 5) * 0.08;
    this.sprite = scene.add.sprite(x, y, 'p_' + key, 'idle_0').setOrigin(15 / 32, 63 / 64).setDepth(opts.depth ?? 30);
    this.facing = opts.facing ?? 1;
    this.setState(opts.state ?? (this.staff ? 'idle' : 'browse'));
    this.reactIdx = Math.floor(Math.random() * 6);
  }
  get x() { return this.sprite.x; }
  get y() { return this.sprite.y; }
  play(a: string) { const k = `p_${this.key}_${a}`; if (this.sprite.anims.currentAnim?.key !== k) this.sprite.play(k, true); }
  setState(s: PState, t = 0) {
    this.state = s; this.t = t;
    const map: Record<PState, string> = { browse: 'browse', walk: 'walk', react: 'shock', flee: 'flee', laugh: 'laugh', gesture: 'gesture', cheer: 'cheer', idle: 'idle' };
    this.play(map[s]);
  }
  say(text: string, life = 1500) {
    if (this.scene.time.now - this.lastLine < 300) return;
    this.lastLine = this.scene.time.now;
    emote(this.scene, this.x, this.y - 62, text, { life });
  }
  /** goose honked at position (distance check done by caller) */
  onHonk(gx: number) {
    if (this.cooldown > 0) return;
    this.cooldown = 1.6;
    const [line, react] = this.staff ? (['HA! CUTE.', 'laugh'] as const) : REACTIONS.honk[this.reactIdx++ % REACTIONS.honk.length];
    this.facing = gx > this.x ? 1 : -1;
    this.say(line);
    this.scene.tweens.add({ targets: this.sprite, y: this.sprite.y - 6, yoyo: true, duration: 110 });
    if (react === 'laugh') { this.setState('laugh', 1.3); SFX.laugh(this.pitch); }
    else if (react === 'flee') { this.setState('flee', 1.1); this.facing = gx > this.x ? -1 : 1; SFX.eek(this.pitch); }
    else { this.setState('react', 0.9); SFX.oh(this.pitch); }
  }
  onBump(gx: number) {
    if (this.cooldown > 0) return;
    this.cooldown = 2.2;
    const [line, react] = REACTIONS.bump[this.reactIdx++ % REACTIONS.bump.length];
    this.facing = gx > this.x ? 1 : -1;
    this.say(line);
    if (react === 'laugh') { this.setState('laugh', 1); SFX.laugh(this.pitch); } else { this.setState('react', 0.7); SFX.hey(this.pitch); }
  }
  cheer() { this.setState('cheer', 99); }
  update(dt: number) {
    this.cooldown -= dt;
    this.t -= dt;
    switch (this.state) {
      case 'browse':
      case 'idle':
        if (!this.staff && this.t <= 0) {
          if (Math.random() < 0.5) { this.target = Phaser.Math.Between(this.range[0], this.range[1]); this.setState('walk'); }
          else this.t = 1.5 + Math.random() * 2.5;
        }
        break;
      case 'walk': {
        const d = this.target - this.x;
        if (Math.abs(d) < 2) { this.setState('browse', 2 + Math.random() * 3); this.facing = Math.random() < 0.5 ? 1 : -1; break; }
        this.facing = Math.sign(d);
        this.sprite.x += Math.sign(d) * this.speed * dt;
        break;
      }
      case 'flee':
        this.sprite.x = Phaser.Math.Clamp(this.sprite.x + this.facing * 85 * dt, this.range[0] - 40, this.range[1] + 40);
        if (this.t <= 0) this.setState('browse', 1.5);
        break;
      case 'react': case 'laugh': case 'gesture':
        if (this.t <= 0) this.setState(this.staff ? 'idle' : 'browse', 1 + Math.random() * 2);
        break;
      case 'cheer': break;
    }
    this.sprite.setFlipX(this.facing < 0);
  }
}
