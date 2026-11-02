/**
 * LEVEL 2a — THE HONKIN' SODA LAB.
 * Console landing → Mix-O-Matic stations → glass wall (dash) → syrup vats (catwalks, conveyor,
 * bubble columns) → zap target gate (Electric Fizz) → steam corridor (time it or shield) →
 * pressure-lever trident lift shaft → SUPER SODA 9000 → portal accident → Soda Dimension.
 */
import Phaser from 'phaser';
import { C } from '../art/palette';
import { LAB, LAB_BG_W, labBgX } from '../art/lab';
import { LevelScene, Rect, SwitchLike } from '../levels/LevelScene';
import { Person } from '../entities/Person';
import { TridentLift } from '../entities/Abilities';
import { emote } from '../entities/Emote';
import { MixResult } from './MixerScene';
import { RECIPE_NAME, POWERS } from '../data/recipes';
import { achieve } from '../data/achievements';
import { GS } from '../systems/gamestate';
import { save, update, addUnique, complete, unlock, StageId } from '../systems/save';
import { shake, flash } from '../systems/camfx';
import { Controls } from '../systems/input';
import { SFX } from '../audio/sfx';
import { MUSIC } from '../audio/music';
import { GerryLab } from '../gameplay/GerryLab';

const F = LAB.FLOOR;
const STATIONS = [{ x: 300, id: 'A' }, { x: 1262, id: 'B' }];

class Target implements SwitchLike {
  on = false; by = ['electric', 'shot'];
  img: Phaser.GameObjects.Image;
  constructor(public s: LabScene, public x: number, public y: number, public onHit: () => void) { this.img = s.add.image(x, y, 'target0').setDepth(30); s.tweens.add({ targets: this.img, scale: 1.08, yoyo: true, repeat: -1, duration: 500 }); }
  rect(): Rect { return { x: this.x - 16, y: this.y - 16, w: 32, h: 32 }; }
  activate() { if (this.on) return; this.on = true; this.img.setTexture('target1'); SFX.chime(); this.s.fx.sparkle(this.x, this.y, 12, C.lim0); this.onHit(); }
}
class Lever implements SwitchLike {
  on = false; by = ['honk', 'interact', 'shot', 'electric'];
  img: Phaser.GameObjects.Image;
  constructor(public s: LabScene, public x: number, public y: number, public onPull: () => void) { this.img = s.add.image(x, y, 'lever0').setOrigin(0.5, 1).setDepth(30); }
  rect(): Rect { return { x: this.x - 14, y: this.y - 30, w: 28, h: 30 }; }
  activate() { if (this.on) return; this.on = true; this.img.setTexture('lever1'); SFX.valve(); this.onPull(); }
}

export class LabScene extends LevelScene {
  stage: StageId = 'lab';
  tech!: Person; tech2!: Person;
  lift!: TridentLift; gateImg!: Phaser.GameObjects.Image; gatePlat!: ReturnType<LevelScene['addPlatform']>;
  conveyorFruit: Phaser.GameObjects.Image[] = []; convSprite!: Phaser.GameObjects.TileSprite;
  steam: { x: number; phase: number; on: boolean; img: Phaser.GameObjects.Image }[] = [];
  jets: { x: number; on: boolean }[] = [];
  mixing = false; t = 0; greeted = { A: false, B: false, gate: false };
  glass: Phaser.GameObjects.Image[] = []; glassBroken = false;
  colT = 0;
  gerry!: Person; gerrySaid = false; gl!: GerryLab;
  constructor() { super('Lab'); }

  create() {
    this.levelName = "LEVEL 2: THE HONKIN' SODA LAB";
    this.initLevel({ w: LAB.W, h: LAB.H, floor: F, bg: 0x1d3c46, spawn: { x: 120, y: F - 44 } });
    this.conveyorFruit = []; this.steam = []; this.jets = []; this.glass = []; this.glassBroken = false; this.mixing = false; this.greeted = { A: false, B: false, gate: false };
    this.buildLab();
    this.finishInit({ music: 'lab' });
    this.lift = new TridentLift(this, this.world, 2004, F - 6, 150);
    this.buildPrompts();
    unlock('lab');
    if (this.registry.get('skipIntro')) { this.registry.set('skipIntro', false); this.phase = 'play'; }
    else this.arrival();
    (window as unknown as { __SIMPS: Record<string, unknown> }).__SIMPS.lab = this;
  }

  buildLab() {
    const P = LAB.PAR;
    this.add.image(0, 0, 'labWall').setOrigin(0).setScrollFactor(P, 1).setDepth(0);
    for (const x of [labBgX(260), labBgX(1700)]) this.add.sprite(x, 60, 'bigFlag0').setScrollFactor(P, 1).setDepth(2).play('bigflag');
    this.add.tileSprite(0, 24, LAB_BG_W, 22, 'bunting').setOrigin(0).setScrollFactor(P, 1).setDepth(3).setAlpha(0.8);
    // walls, ceiling, floors (with the vat pit gap)
    this.addPlatform(-40, 0, 52, LAB.H, 'solid', 'wallL'); this.addPlatform(LAB.W - 12, 0, 60, LAB.H, 'solid', 'wallR');
    this.addPlatform(-40, -40, LAB.W + 80, 62, 'solid', 'ceiling');
    for (const [x0, x1] of [[-40, 680], [1180, LAB.W + 40]]) { this.addPlatform(x0, F, x1 - x0, 40, 'solid', 'floor'); this.add.tileSprite(Math.max(0, x0), F, x1 - Math.max(0, x0), 30, 'labFloor').setOrigin(0).setDepth(15); }
    // console (landing pad)
    this.addPlatform(72, F - 44, 96, 44, 'solid', 'console');
    this.add.image(72, F, 'labConsole').setOrigin(0, 1).setDepth(28);
    // Mix-O-Matic stations
    for (const st of STATIONS) {
      this.add.image(st.x, F, 'mixer').setOrigin(0.5, 1).setDepth(27);
      this.add.image(st.x, F - 100, 'glow64').setTint(C.lim0).setBlendMode(Phaser.BlendModes.ADD).setAlpha(0.25).setDepth(26);
    }
    this.tech = new Person(this, 'lab_tech', 400, F, { staff: true, facing: -1 }); this.people.push(this.tech);
    this.tech2 = new Person(this, 'lab_tech', 1340, F, { staff: true, facing: 1 }); this.people.push(this.tech2);
    this.gerry = new Person(this, 'gerry', 2372, F, { staff: true, facing: -1, depth: 28 }); this.people.push(this.gerry); this.gerrySaid = false;
    // fragile glass wall + solid bulkhead above
    this.addPlatform(600, 22, 44, 236, 'solid', 'bulkhead');
    const bh = this.add.graphics().setDepth(29); bh.fillStyle(C.st3).fillRect(600, 22, 44, 236).fillStyle(C.st4).fillRect(600, 250, 44, 8);
    for (let y = 40; y < 250; y += 30) bh.fillStyle(C.gold1).fillRect(604, y, 36, 3);
    const glassPlat = this.addPlatform(600, 258, 44, F - 258, 'solid', 'glass');
    for (let r = 0; r < 6; r++) for (let c = 0; c < 2; c++) this.glass.push(this.add.image(611 + c * 22, F - 11 - r * 22, 'glassBlock').setDepth(30));
    this.add.image(622, 236, 'signDelivery').setDepth(31).setVisible(false);
    this.breakables.push({ broken: false, rect: () => ({ x: 600, y: 258, w: 44, h: F - 258 }), by: ['dash'], smash: (dir: number) => {
      const b = this.breakables[0]; b.broken = true; this.glassBroken = true; this.world.remove(glassPlat);
      SFX.crash(); for (let i = 0; i < 5; i++) SFX.clink(1 + Math.random());
      this.glass.forEach((gl, i) => { this.tweens.add({ targets: gl, x: gl.x + dir * (30 + Math.random() * 90), y: F - 6, angle: dir * (90 + Math.random() * 200), alpha: 0.6, scale: 0.6, duration: 500 + i * 30, ease: 'Quad.Out' }); });
      this.fx.sparkle(622, F - 60, 16, C.gl0);
      this.tech.say('MY BEAUTIFUL GLASS!', 1500);
    } });
    // ---- vat section 680..1180
    const vats: [number, number, string][] = [[680, 860, 'syrup_cherry'], [860, 1040, 'syrup_mango'], [1040, 1180, 'syrup_blue']];
    for (const [x0, x1, tex] of vats) {
      const ts = this.add.tileSprite(x0, F + 4, x1 - x0, 14, tex).setOrigin(0).setDepth(16);
      this.tweens.add({ targets: ts, tilePositionX: 64, duration: 4000, repeat: -1 });
      this.add.rectangle(x0, F + 18, x1 - x0, 30, tex === 'syrup_blue' ? C.blu3 : tex === 'syrup_mango' ? C.mng2 : C.chr3).setOrigin(0).setDepth(16);
    }
    const vg = this.add.graphics().setDepth(17); vg.fillStyle(C.st3); for (const x of [676, 856, 1036, 1176]) vg.fillRect(x, F - 6, 8, 40);
    this.hazards.push({ rect: { x: 684, y: F + 6, w: 492, h: 30 }, kind: 'pit' });
    const walks: [number, number, number][] = [[700, 748, 340], [780, 828, 306], [1050, 1098, 296], [1124, 1178, 338]];
    for (const [x0, x1, y] of walks) { this.addPlatform(x0, y, x1 - x0, 5, 'oneway', 'catwalk'); this.add.image(x0, y, 'catwalk48').setOrigin(0).setDepth(27); this.add.rectangle(x0 + 4, 22, 1, y - 22, C.st3).setOrigin(0).setDepth(26); this.add.rectangle(x1 - 4, 22, 1, y - 22, C.st3).setOrigin(0).setDepth(26); }
    // conveyor belt (moving surface, carries the goose) with fruit + robot arms above
    this.addPlatform(860, 326, 160, 8, 'oneway', 'conveyor');
    this.convSprite = this.add.tileSprite(860, 326, 160, 12, 'conveyor').setOrigin(0).setDepth(27);
    for (let i = 0; i < 4; i++) this.add.sprite(880 + i * 40, 48, 'arm0').setOrigin(0.5, 0).setDepth(25).play({ key: 'arm', startFrame: i % 4 });
    const fr = ['fruit_cherry', 'fruit_lemon', 'fruit_mango', 'fruit_coconut', 'fruit_strawberry'];
    for (let i = 0; i < 6; i++) this.conveyorFruit.push(this.add.image(866 + i * 28, 320, fr[i % 5]).setDepth(28));
    // Cloud-Nine shortcut drops high above the vats
    this.addDropLine(700, 1160, 200, 7);
    this.addPickup('leaf', 940, 176);
    // ---- station B, zap gate
    this.addCheckpoint(1214, F);
    this.addPlatform(1228, 150, 44, 5, 'oneway', 'secret'); const sg = this.add.graphics().setDepth(27); sg.fillStyle(C.st2).fillRect(1228, 150, 44, 5);
    this.addPickup('card', 1250, 134, 'root_beer_float');
    this.addPlatform(1480, 22, 18, 238, 'solid', 'gateTop');
    const gt = this.add.graphics().setDepth(29); gt.fillStyle(C.st3).fillRect(1480, 22, 18, 238);
    this.gatePlat = this.addPlatform(1480, 260, 18, 130, 'solid', 'gate');
    this.gateImg = this.add.image(1480, 260, 'gate').setOrigin(0).setDepth(30);
    this.switches.push(new Target(this, 1420, 176, () => this.openGate()));
    this.add.image(1420, 206, 'trident22').setDepth(29).setAlpha(0.6);
    // ---- steam corridor
    for (const [i, x] of [1560, 1640, 1720, 1800].entries()) {
      const img = this.add.image(x, F, 'ventSteam').setOrigin(0.5, 1).setDepth(20);
      const v = { x, phase: i * 0.55, on: false, img };
      this.steam.push(v);
      this.hazards.push({ rect: { x: x - 10, y: F - 88, w: 20, h: 88 }, kind: 'steam', active: () => v.on });
    }
    this.addCheckpoint(1856, F);
    // ---- lift shaft
    this.switches.push(new Lever(this, 1928, F, () => { this.lift.running = true; this.say('CLUNK!', 1928, F - 40, 800); this.game.events.emit('hud:toast', 'TRIDENT LIFT ONLINE!', C.red0); }));
    for (const x of [2080]) { this.add.image(x, F, 'ventJet').setOrigin(0.5, 1).setDepth(20); const j = { x, on: false }; this.jets.push(j); this.hazards.push({ rect: { x: x - 10, y: F - 150, w: 20, h: 150 }, kind: 'jet', strength: 420, active: () => j.on }); }
    for (const [x0, x1, y] of [[2060, 2110, 236], [1880, 1940, 210]] as [number, number, number][]) { this.addPlatform(x0, y, x1 - x0, 5, 'oneway', 'ledge'); this.add.image(x0, y, 'catwalk48').setOrigin(0).setDepth(27); }
    this.addPickup('leaf', 1904, 194);
    this.addPickup('bottle', 1990, 74);
    this.addPlatform(2030, 150, 380, 5, 'oneway', 'upper');
    this.add.tileSprite(2030, 150, 380, 10, 'catwalk80').setOrigin(0).setDepth(27);
    this.addDropLine(2060, 2380, 136, 8);
    this.addPickup('badge', 2448, 112);
    // ---- super soda machine
    this.add.image(2600, F, 'superMachine').setOrigin(0.5, 1).setDepth(27);
    this.add.image(2600, F - 120, 'glow128').setTint(C.red0).setBlendMode(Phaser.BlendModes.ADD).setAlpha(0.2).setDepth(26);
    this.addPickup('leaf', 2760, F - 16);
    this.addCrackedWall(1660, F, 'star'); this.addHighStash(2560, 120, 'star');
    this.gl = new GerryLab(this, this.gerry, 2290, F, [[2396, 150], [2085, 236], [2730, F]]);
    // recipe cards along the way
    this.addPickup('card', 230, F - 16, 'cherry_rocket');
    this.addPickup('card', 1074, 280, 'tropical_launch');
    this.addPickup('card', 760, 320, 'cloud_nine');
    this.addPickup('card', 1310, F - 16, 'electric_fizz');
    this.addPickup('card', 1520, F - 16, 'dark_foam_shield');
    // drops
    this.addDropLine(190, 280, F - 14, 4); this.addDropLine(420, 560, F - 14, 6); this.addDropLine(706, 740, 324, 3); this.addDropLine(786, 820, 290, 3);
    this.addDropLine(1200, 1440, F - 14, 6); this.addDropLine(1540, 1820, F - 14, 8); this.addDropLine(2150, 2560, F - 14, 9);
    // ambient lights
    for (let x = 140; x < LAB.W; x += 240) this.add.image(x, 30, 'glow128').setOrigin(0.5, 0.1).setScale(1.2, 2.2).setTint(0x9ff0ff).setAlpha(0.13).setBlendMode(Phaser.BlendModes.ADD).setDepth(57);
    this.add.particles(0, 0, 'dot2', { x: { min: 0, max: LAB.W }, y: F + 2, lifespan: 4000, speedY: { min: -30, max: -10 }, speedX: { min: -4, max: 4 }, alpha: { start: 0.6, end: 0 }, frequency: 90, tint: [C.bub1, C.lim0, C.chr0] }).setDepth(58);
  }

  buildPrompts() {
    const g = this.goose;
    for (const st of STATIONS) this.addPrompt(this.key('use'), () => this.nearStation() === st && this.phase === 'play', () => false, () => ({ x: st.x, y: F - 112 }));
    this.addPrompt(this.key('power'), () => !this.glassBroken && g.x > 520 && g.x < 600, () => this.glassBroken, () => ({ x: g.x, y: g.y - 46 }));
    this.addPrompt(this.key('honk'), () => !this.lift.running && Math.abs(g.x - 1928) < 50, () => this.lift.running, () => ({ x: 1928, y: F - 48 }));
    this.addPrompt(this.key('use'), () => Math.abs(g.x - 2600) < 80 && g.y > F - 10 && this.phase === 'play' && this.gl.state === 'done', () => false, () => ({ x: 2600, y: F - 182 }));
    this.addPrompt(this.key('use'), () => this.gl.state === 'collect' && !!this.gl.carried && this.gl.near() && this.phase === 'play', () => this.gl.state !== 'collect', () => ({ x: g.x, y: g.y - 46 }));
    this.addPrompt(this.key('honk'), () => this.gl.state === 'carb' && this.gl.near(), () => this.gl.state !== 'carb', () => ({ x: 2290, y: F - 150 }));
  }
  nearStation() { const g = this.goose; return STATIONS.find((s) => Math.abs(g.x - s.x) < 40 && g.y > F - 6) ?? null; }

  arrival() {
    const g = this.goose;
    this.phase = 'cutscene';
    g.mode = 'ride';
    const bub = this.add.image(120, -30, 'bubble96').setDepth(47).setScale(0.78).setTint(0xf2fbff);
    const ride = { x: 120, y: -10 }; g.ride = ride;
    this.tweens.add({ targets: bub, y: F - 66, duration: 1600, ease: 'Sine.Out', onUpdate: () => { ride.x = bub.x; ride.y = bub.y + 22; } });
    this.time.delayedCall(1700, () => {
      bub.destroy(); SFX.bigPop(); this.fx.bubbles(120, F - 66, 14);
      g.mode = 'play'; g.ride = null; g.body.vy = 0;
    });
    this.time.delayedCall(2100, () => {
      // every machine switches on at once
      flash(this, 200, 160, 255, 220); shake(this, 600, 0.006);
      SFX.mixer(1.5); SFX.rumble(1); SFX.fizz(1, 1.5);
      MUSIC.setIntensity(1);
      for (let i = 0; i < 10; i++) this.time.delayedCall(i * 90, () => this.fx.sparkle(100 + Math.random() * 600, 60 + Math.random() * 200, 4, [C.lim0, C.blu0, C.red0][i % 3]));
      g.playLoop('celebrate'); SFX.honk(1.1); this.fx.honk(g.x + 10, g.y - 30, 1, true);
      this.tech.setState('react', 1.5); this.tech.say('A GOOSE IN THE LAB?!', 1800); SFX.oh(1.1);
    });
    this.time.delayedCall(3600, () => { g.playLoop('idle'); this.phase = 'play'; this.tech.say('TRY THE MIX-O-MATIC!', 2000); });
  }

  openGate() {
    if (!this.gatePlat.active) return;
    SFX.valve(); SFX.rumble(0.8);
    this.tweens.add({ targets: this.gateImg, y: 130, duration: 900, ease: 'Cubic.InOut', onComplete: () => this.world.remove(this.gatePlat) });
    this.game.events.emit('hud:toast', 'GATE OPEN!', C.lim0);
    this.tech2.setState('cheer', 1.5);
  }

  onHonkLevel(x: number) { this.gl.onHonk(x); }
  hintText(): string | null {
    const g = this.goose, use = this.touch ? 'SIP' : 'E', pw = this.touch ? 'POWER' : 'C';
    if (!this.glassBroken && g.x < 600) return `MIX A DRINK AT A MIX-O-MATIC (${use}). COLA OR CHERRY ROCKET LETS YOU DASH (${pw}) THROUGH THE GLASS WALL.`;
    if (this.gatePlat.active && g.x < 1480) return 'ZAP THE TARGET WITH ELECTRIC FIZZ (BLUE RASPBERRY + LEMON LIME) TO OPEN THE GATE.';
    if (!this.lift.running) return 'HONK THE LEVER NEXT TO THE LIFT SHAFT, THEN RIDE THE LIFT UP.';
    const gl = this.gl;
    if (gl.state === 'idle') return "FIND GERRY BY HIS MACHINE, PAST THE LIFT.";
    if (gl.state === 'collect') return gl.carried ? `POUR THE SAMPLE INTO THE TANK OF THE SAME COLOUR (${use}).` : 'FIND THE GLOWING SAMPLES: UP ON THE CATWALK, ABOVE THE STEAM JET, AND PAST THE SUPER SODA 9000.';
    if (gl.state === 'carb') return "HONK BY GERRY'S MACHINE WHEN THE NEEDLE IS IN THE GREEN.";
    if (gl.state === 'done') return `AT THE SUPER SODA 9000 PRESS ${use}, THEN MIX COLA + CREAM SODA + BLACK CHERRY WITH MAX FIZZ.`;
    return null;
  }
  onInteract() {
    const st = this.nearStation();
    if (st) { this.openMixer('normal'); return true; }
    if (this.gl.onInteract()) return true;
    if (Math.abs(this.goose.x - 2600) < 80 && this.goose.y > F - 10) {
      if (this.gl.state !== 'done') { this.gerry.lastLine = 0; this.gerry.say(this.gl.state === 'idle' ? 'GOOSE! OVER HERE FIRST!' : 'FINISH MY EXPERIMENT FIRST!', 1800); this.gerry.act('point', 1); return true; }
      this.openMixer('super'); return true;
    }
    return false;
  }
  openMixer(mode: 'normal' | 'super') {
    if (this.mixing) return;
    this.mixing = true;
    this.goose.body.vx = 0;
    this.phase = 'picker';
    this.scene.pause();
    this.scene.launch('Mixer', { mode, onDone: (r: MixResult) => { this.scene.resume(); this.mixing = false; this.phase = 'play'; Controls.consumeAll(); this.applyMix(r); } });
    this.scene.bringToTop('Mixer');
  }
  applyMix(r: MixResult & { cancelled?: boolean }) {
    if (r.cancelled) return;
    const g = this.goose;
    r.picks.forEach((p) => addUnique('flavors', p));
    if (r.isSuper) return this.portal();
    if (r.recipe) {
      const id = r.recipe.id;
      const rank = { over: 0, good: 1, perfect: 2 };
      update((s) => { const prev = s.recipes[id]; const best = (prev?.best ?? 0) + 1; s.recipes[id] = { quality: !prev || rank[r.quality] > rank[prev.quality] ? r.quality : prev.quality, count: (prev?.count ?? 0) + 1, best: Math.max(best, prev?.best ?? 0) }; });
      if (r.recipe.secret) achieve('secret_recipe');
      if (Object.keys(save().recipes).length >= 5) achieve('mixologist');
      this.game.events.emit('hud:toast', `RECIPE: ${RECIPE_NAME[id]}`, C.gold1, 'SAVED IN THE RECIPE JOURNAL');
    }
    if (r.quality === 'perfect') { achieve('perfect_mix'); GS.addScore(500); }
    // the goose reacts to the drink
    g.mode = 'script'; this.phase = 'cutscene';
    g.playOnce('drink'); SFX.slurp();
    this.time.delayedCall(700, () => { g.playOnce('swallow'); SFX.gulp(); });
    this.time.delayedCall(1400, () => {
      if (r.quality === 'over') {
        SFX.explosion(); shake(this, 400, 0.008);
        for (let i = 0; i < 14; i++) this.fx.steamE.explode(1, g.x + (Math.random() - 0.5) * 50, g.y - Math.random() * 40);
        g.playLoop('hurt'); emote(this, g.x, g.y - 46, 'TOO FOAMY!', { life: 1200 });
      } else if (r.quality === 'perfect') { g.playLoop('celebrate'); this.fx.hearts(g.x, g.y - 30, 3); this.fx.confetti(g.x, g.y - 30, 16); SFX.chime(); }
      else { g.playLoop('reactFizz'); SFX.fizz(0.8, 1); }
    });
    this.time.delayedCall(2600, () => {
      g.mode = 'play'; g.playLoop('idle'); this.phase = 'play';
      this.setPower(r.power, r.quality === 'perfect' ? 1.5 : r.quality === 'over' ? 0.6 : 1);
      this.game.events.emit('hud:power', r.power, this.powerT, POWERS[r.power].duration);
    });
  }

  /** The SUPER SODA → rainbow bubble → portal → Soda Dimension. */
  portal() {
    const g = this.goose;
    this.phase = 'cutscene'; g.mode = 'script';
    MUSIC.setIntensity(2);
    SFX.rumble(2); SFX.mixer(2); shake(this, 2000, 0.006);
    // bottles levitate
    for (let i = 0; i < 10; i++) {
      const b = this.add.image(2480 + Math.random() * 240, F - 10, 'bottle' + (i % 8)).setDepth(48);
      this.tweens.add({ targets: b, y: F - 120 - Math.random() * 120, angle: (Math.random() - 0.5) * 120, duration: 1800 + Math.random() * 800, ease: 'Sine.Out' });
    }
    this.time.delayedCall(900, () => { g.playOnce('drink'); SFX.slurp(); this.say('*SIIIIP*', g.x, g.y - 46, 1000); });
    this.time.delayedCall(1800, () => { g.playOnce('swallow'); SFX.gulp(); });
    const glow = this.add.image(g.x, g.y - 20, 'glow128').setBlendMode(Phaser.BlendModes.ADD).setDepth(49).setAlpha(0).setScale(0.6);
    this.tweens.add({ targets: glow, alpha: 0.9, duration: 800, delay: 2300, yoyo: true, repeat: 3 });
    const bub = this.add.image(g.x, g.y - 22, 'bubble96').setDepth(50).setScale(0.1);
    this.time.delayedCall(2600, () => { g.playLoop('reactFizz'); SFX.portal(); });
    this.tweens.add({ targets: bub, scale: 9, delay: 2800, duration: 2200, ease: 'Quad.In', onUpdate: () => bub.setTint(Phaser.Display.Color.HSVToRGB((this.time.now / 600) % 1, 0.35, 1).color) });
    this.time.delayedCall(5000, () => {
      flash(this, 300);
      bub.destroy();
      const ring = this.add.graphics().setDepth(60).setScrollFactor(0);
      const t0 = this.time.now;
      this.events.on('postupdate', () => {
        if (!ring.active) return;
        const t = (this.time.now - t0) / 1000;
        ring.clear();
        for (let k = 0; k < 9; k++) {
          const r = (k * 18 + t * 80) % 170;
          ring.lineStyle(6, Phaser.Display.Color.HSVToRGB((k / 9 + t * 0.5) % 1, 0.8, 1).color, 0.9).strokeCircle(240, 135, 170 - r);
        }
      });
      g.mode = 'ride'; g.ride = { x: g.x, y: g.y };
      this.tweens.add({ targets: g.sprite, angle: 720, scale: 0, duration: 1600, ease: 'Quad.In' });
      this.say('HOOOONK!', g.x, g.y - 50, 1400); SFX.honk(1.6);
      complete('lab'); unlock('dimension');
      this.time.delayedCall(1700, () => this.goTo('Dimension'));
    });
  }

  stepLevel(dt: number) {
    this.lift.step(dt);
    // conveyor pushes things standing on it
    if (this.goose.body.ground?.tag === 'conveyor' && this.goose.body.onGround) this.goose.body.x += 34 * dt;
  }
  frameLevel(dt: number) {
    this.t += dt;
    this.lift.render();
    this.convSprite.tilePositionX -= 34 * dt;
    for (const f of this.conveyorFruit) { f.x += 34 * dt; if (f.x > 1022) { this.fx.drops(f.x, F, C.mng1, 4); SFX.splash(0.4); f.x = 866; } }
    for (const v of this.steam) {
      const c = (this.t + v.phase) % 2.2; const was = v.on; v.on = c < 1;
      if (v.on && Math.random() < dt * 30) this.fx.steamE.explode(1, v.x + (Math.random() - 0.5) * 8, F - 10 - Math.random() * 60);
      if (v.on && !was && Math.abs(v.x - this.goose.x) < 200) SFX.hiss(0.9);
      v.img.setTint(v.on ? 0xffb0b0 : 0xffffff);
    }
    for (const j of this.jets) { j.on = (this.t % 3) < 1.6; if (j.on && Math.random() < dt * 25) this.fx.fizz(j.x, F - 10 - Math.random() * 100, 3); }
    this.colT -= dt;
    if (this.colT <= 0) { this.colT = 1.7; for (const x of [760, 960]) this.bubbles.spawn(x, F + 8, 15, 'rise', { vy: -30, maxStomps: 3, tint: x === 760 ? 0xffe0ea : 0xfff0d0 }); }
    // tutorial chatter
    const g = this.goose;
    if (!this.greeted.A && Math.abs(g.x - 300) < 90 && this.phase === 'play') { this.greeted.A = true; this.tech.say('BASE + SYRUP + FIZZ. PUMP IN THE GREEN!', 2600); }
    this.gl.update(dt);
    if (this.gl.state === 'done' && !this.gerrySaid && Math.abs(g.x - 2560) < 100 && this.phase === 'play') { this.gerrySaid = true; this.gerry.say('THE SUPER SODA 9000. GERRY APPROVES... MOSTLY.', 2600); this.gerry.setState('gesture', 2); }
    if (!this.greeted.B && Math.abs(g.x - 1300) < 120 && this.phase === 'play') { this.greeted.B = true; this.tech2.say('THAT TARGET NEEDS AN ELECTRIC ZAP!', 2600); }
    // electric fizz homes in on zap targets
    for (const s of this.shots) if (s.active && s.kind === 'electric') for (const sw of this.switches) if (!sw.on && sw.by.includes('electric') && sw instanceof Target) {
      const dx = sw.x - s.x, dy = sw.y - s.y, d = Math.hypot(dx, dy);
      if (d < 260) { s.vx += (dx / d) * 900 * dt; s.vy += (dy / d) * 900 * dt; const sp = Math.hypot(s.vx, s.vy); if (sp > 340) { s.vx *= 340 / sp; s.vy *= 340 / sp; } }
    }
  }
}
