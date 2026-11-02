/** All sound effects — synthesised, original. */
import { AE, osc, noise } from './engine';

function out() { return AE.ensure() ? AE.sfx : null; }
const R = (a: number, b: number) => a + Math.random() * (b - a);

function formantVoice(t: number, f0: number, f1: number, dur: number, formants: [number, number][], gain = 0.25, type: OscillatorType = 'sawtooth') {
  const ctx = AE.ctx!, o = out()!;
  const src = ctx.createOscillator(); src.type = type;
  src.frequency.setValueAtTime(f0, t); src.frequency.exponentialRampToValueAtTime(f1, t + dur);
  const vib = ctx.createOscillator(), vg = ctx.createGain(); vib.frequency.value = 7; vg.gain.value = f0 * 0.03; vib.connect(vg); vg.connect(src.frequency);
  const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(gain, t + 0.02); g.gain.setValueAtTime(gain, t + dur * 0.6); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  for (const [f, q] of formants) { const bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = f; bp.Q.value = q; src.connect(bp); bp.connect(g); }
  g.connect(o);
  src.start(t); vib.start(t); src.stop(t + dur + 0.05); vib.stop(t + dur + 0.05);
}

export const SFX = {
  honk(size = 1) {
    const o = out(); if (!o) return;
    const t = AE.now, ctx = AE.ctx!;
    const dur = 0.26 * (0.8 + size * 0.4) + (size > 1.5 ? 0.35 : 0);
    const p = R(0.95, 1.06) / Math.max(0.8, Math.min(1.3, size * 0.9));
    const shaper = ctx.createWaveShaper();
    const curve = new Float32Array(256); for (let i = 0; i < 256; i++) { const x = i / 128 - 1; curve[i] = Math.tanh(x * 4); } shaper.curve = curve;
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(0.15 * Math.min(1.5, size), t + 0.015); g.gain.setValueAtTime(0.14 * Math.min(1.5, size), t + dur * 0.55); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    const f1 = ctx.createBiquadFilter(); f1.type = 'bandpass'; f1.frequency.value = 1150; f1.Q.value = 3;
    const f2 = ctx.createBiquadFilter(); f2.type = 'bandpass'; f2.frequency.value = 2500; f2.Q.value = 4;
    const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 3800;
    for (const [mul, type] of [[1, 'sawtooth'], [1.007, 'sawtooth'], [0.5, 'square']] as [number, OscillatorType][]) {
      const s = ctx.createOscillator(); s.type = type;
      s.frequency.setValueAtTime(380 * p * mul, t); s.frequency.linearRampToValueAtTime(420 * p * mul, t + 0.04); s.frequency.exponentialRampToValueAtTime(300 * p * mul, t + dur);
      s.connect(shaper); s.start(t); s.stop(t + dur + 0.05);
    }
    shaper.connect(f1); shaper.connect(f2); shaper.connect(lp);
    const mix = ctx.createGain(); mix.gain.value = 0.5;
    f1.connect(g); f2.connect(mix); mix.connect(g); lp.connect(mix);
    g.connect(o);
    noise(t, 0.08, o, { f: 3000, q: 1, gain: 0.06 });
  },
  step(alt = false) { const o = out(); if (!o) return; const t = AE.now; noise(t, 0.04, o, { type: 'lowpass', f: alt ? 900 : 700, gain: 0.07 }); osc('sine', alt ? 150 : 130, t, 0.05, o, { f1: 70, gain: 0.08 }); },
  jump() { const o = out(); if (!o) return; const t = AE.now; osc('square', 260, t, 0.13, o, { f1: 560, gain: 0.07 }); noise(t, 0.12, o, { f: 1400, f1: 600, gain: 0.05 }); },
  flap() { const o = out(); if (!o) return; const t = AE.now; noise(t, 0.08, o, { f: 900, f1: 400, q: 0.7, gain: 0.16 }); },
  land() { const o = out(); if (!o) return; const t = AE.now; osc('sine', 110, t, 0.12, o, { f1: 45, gain: 0.18 }); noise(t, 0.06, o, { type: 'lowpass', f: 600, gain: 0.08 }); },
  clink(pitch = 1) { const o = out(); if (!o) return; const t = AE.now; for (const [f, g] of [[2400, 0.08], [3170, 0.05], [4430, 0.04], [5900, 0.02]]) osc('sine', f * pitch * R(0.98, 1.02), t, 0.35, o, { gain: g }); },
  slurp() { const o = out(); if (!o) return; const t = AE.now; const n = noise(t, 0.7, o, { f: 600, f1: 1800, q: 4, gain: 0.12 }); const ctx = AE.ctx!; const l = ctx.createOscillator(), lg = ctx.createGain(); l.frequency.value = 16; lg.gain.value = 0.1; l.connect(lg); lg.connect(n.g.gain); l.start(t); l.stop(t + 0.75); },
  gulp() { const o = out(); if (!o) return; const t = AE.now; osc('sine', 340, t, 0.16, o, { f1: 110, gain: 0.3 }); osc('sine', 260, t + 0.2, 0.14, o, { f1: 90, gain: 0.22 }); },
  pour() { const o = out(); if (!o) return; const t = AE.now; noise(t, 0.9, o, { f: 1400, q: 2, gain: 0.08, attack: 0.1 }); for (let i = 0; i < 6; i++) osc('sine', R(500, 900), t + i * 0.12, 0.06, o, { f1: R(1200, 1600), gain: 0.05 }); },
  fizz(dur = 0.6, amt = 1) { const o = out(); if (!o) return; const t = AE.now; for (let i = 0; i < 24 * amt; i++) noise(t + Math.random() * dur, 0.012, o, { type: 'highpass', f: R(3000, 7000), gain: R(0.03, 0.08) }); noise(t, dur, o, { type: 'highpass', f: 5000, gain: 0.03 * amt, attack: 0.05 }); },
  bubble() { const o = out(); if (!o) return; const t = AE.now; osc('sine', R(220, 300), t, 0.22, o, { f1: R(700, 900), gain: 0.18 }); osc('sine', R(500, 600), t + 0.05, 0.15, o, { f1: 1200, gain: 0.06 }); },
  pop(size = 1) { const o = out(); if (!o) return; const t = AE.now; noise(t, 0.04, o, { type: 'highpass', f: 1800 / size, gain: 0.18 }); osc('sine', 1300 / Math.sqrt(size), t, 0.05, o, { f1: 260, gain: 0.16 }); },
  oh(pitch = 1) { const o = out(); if (!o) return; formantVoice(AE.now, 210 * pitch, 300 * pitch, 0.32, [[520, 6], [900, 7]], 0.32); },
  hey(pitch = 1) { const o = out(); if (!o) return; formantVoice(AE.now, 230 * pitch, 190 * pitch, 0.26, [[520, 6], [1850, 8]], 0.3); },
  laugh(pitch = 1) { const o = out(); if (!o) return; for (let i = 0; i < 4; i++) formantVoice(AE.now + i * 0.13, (260 - i * 14) * pitch, (230 - i * 14) * pitch, 0.1, [[800, 5], [1250, 6]], 0.26); },
  eek(pitch = 1) { const o = out(); if (!o) return; formantVoice(AE.now, 520 * pitch, 760 * pitch, 0.24, [[350, 6], [2300, 8]], 0.26, 'triangle'); },
  cheer() { const o = out(); if (!o) return; const t = AE.now; for (let i = 0; i < 5; i++) formantVoice(t + i * 0.04, R(200, 320), R(300, 420), 0.5, [[700, 5], [1200, 6]], 0.12); noise(t, 0.8, o, { f: 2500, q: 0.5, gain: 0.05, attack: 0.1 }); },
  fountainStart(level = 1) { const o = out(); if (!o) return; const t = AE.now; osc('sawtooth', 48, t, 1.6, o, { f1: 70, gain: 0.16, attack: 0.2 }); noise(t, 1.4, o, { type: 'lowpass', f: 300, gain: 0.12, attack: 0.2 }); osc('sine', 420, t + 0.2, 1.3, o, { f1: level > 1 ? 2400 : 1400, gain: 0.07, attack: 0.3 }); },
  hiss(dur = 1) { const o = out(); if (!o) return; noise(AE.now, dur, o, { type: 'highpass', f: 3500, gain: 0.1, attack: 0.05 }); },
  bigPop() { const o = out(); if (!o) return; const t = AE.now; noise(t, 0.4, o, { type: 'lowpass', f: 2000, f1: 200, gain: 0.35 }); osc('sine', 160, t, 0.4, o, { f1: 40, gain: 0.35 }); this.fizz(1.2, 1.5); },
  collect(n = 0) { const o = out(); if (!o) return; const t = AE.now; const b = 1 + (n % 4) * 0.06; [1046, 1318, 1568].forEach((f, i) => osc('square', f * b, t + i * 0.045, 0.1, o, { gain: 0.05 })); },
  golden() { const o = out(); if (!o) return; const t = AE.now; [784, 988, 1175, 1568, 1976, 2349].forEach((f, i) => osc('triangle', f, t + i * 0.07, 0.35, o, { gain: 0.09 })); },
  burp() { const o = out(); if (!o) return; const t = AE.now; formantVoice(t, 95, 70, 0.45, [[400, 4], [700, 5]], 0.4, 'sawtooth'); noise(t, 0.4, o, { type: 'lowpass', f: 500, gain: 0.08 }); },
  dash() { const o = out(); if (!o) return; const t = AE.now; noise(t, 0.25, o, { f: 600, f1: 3000, q: 0.8, gain: 0.18 }); this.fizz(0.35, 0.8); },
  foam() { const o = out(); if (!o) return; const t = AE.now; noise(t, 0.5, o, { type: 'lowpass', f: 900, gain: 0.12, attack: 0.08 }); osc('sine', 300, t, 0.4, o, { f1: 700, gain: 0.08, attack: 0.05 }); },
  shoot() { const o = out(); if (!o) return; const t = AE.now; osc('sine', 950, t, 0.16, o, { f1: 380, gain: 0.18 }); osc('square', 480, t, 0.06, o, { f1: 200, gain: 0.04 }); },
  bounce() { const o = out(); if (!o) return; osc('sine', R(380, 460), AE.now, 0.1, o, { f1: 800, gain: 0.1 }); },
  crash() { const o = out(); if (!o) return; const t = AE.now; for (let i = 0; i < 4; i++) { noise(t + i * 0.08, 0.14, o, { type: 'lowpass', f: 700, gain: 0.25 }); osc('sine', 120 - i * 15, t + i * 0.08, 0.12, o, { f1: 50, gain: 0.2 }); } },
  valve() { const o = out(); if (!o) return; const t = AE.now; osc('sawtooth', 620, t, 0.5, o, { f1: 760, gain: 0.05, curve: 'lin' }); osc('square', 90, t + 0.45, 0.12, o, { f1: 60, gain: 0.15 }); this.clink(0.5); },
  door() { const o = out(); if (!o) return; const t = AE.now; osc('sawtooth', 160, t, 0.5, o, { f1: 110, gain: 0.04 }); [1760, 2640].forEach((f) => osc('sine', f, t + 0.05, 0.9, o, { gain: 0.08 })); },
  hurt() { const o = out(); if (!o) return; const t = AE.now; osc('square', 640, t, 0.25, o, { f1: 160, gain: 0.1 }); [1800, 2100, 1800].forEach((f, i) => osc('sine', f, t + 0.25 + i * 0.09, 0.07, o, { gain: 0.05 })); },
  powerup() { const o = out(); if (!o) return; const t = AE.now; [523, 659, 784, 1046, 1318].forEach((f, i) => osc('square', f, t + i * 0.06, 0.16, o, { gain: 0.06 })); },
  powerdown() { const o = out(); if (!o) return; const t = AE.now; [784, 659, 523].forEach((f, i) => osc('triangle', f, t + i * 0.07, 0.16, o, { gain: 0.07 })); },
  pump() { const o = out(); if (!o) return; const t = AE.now; noise(t, 0.18, o, { f: 500, f1: 1500, q: 3, gain: 0.12 }); osc('sine', 180, t, 0.14, o, { f1: 90, gain: 0.12 }); },
  mixer(dur = 1) { const o = out(); if (!o) return; const t = AE.now; osc('sawtooth', 70, t, dur, o, { f1: 140, gain: 0.05, attack: 0.1, curve: 'lin' }); noise(t, dur, o, { f: 900, q: 2, gain: 0.05, attack: 0.1 }); },
  explosion() { const o = out(); if (!o) return; const t = AE.now; noise(t, 1.2, o, { type: 'lowpass', f: 1800, f1: 120, gain: 0.4 }); osc('sine', 120, t, 1, o, { f1: 30, gain: 0.35 }); this.fizz(1.4, 2); },
  portal() { const o = out(); if (!o) return; const t = AE.now; for (let i = 0; i < 3; i++) osc('triangle', 200 + i * 150, t + i * 0.1, 1.6, o, { f1: 1600 + i * 400, gain: 0.08, attack: 0.3 }); noise(t, 1.8, o, { f: 400, f1: 4000, q: 1, gain: 0.08, attack: 0.4 }); },
  espresso(dur = 1.5) { const o = out(); if (!o) return; const t = AE.now; noise(t, dur, o, { f: 700, q: 1.5, gain: 0.08, attack: 0.2 }); osc('square', 55, t, dur, o, { gain: 0.03, attack: 0.2 }); },
  froth(dur = 1.2) { const o = out(); if (!o) return; const t = AE.now; noise(t, dur, o, { type: 'highpass', f: 2500, gain: 0.08, attack: 0.15 }); for (let i = 0; i < 10; i++) osc('sine', R(800, 1400), t + i * dur / 10, 0.05, o, { gain: 0.03 }); },
  grind() { const o = out(); if (!o) return; const t = AE.now; for (let i = 0; i < 8; i++) noise(t + i * 0.06, 0.05, o, { f: R(1200, 2400), q: 3, gain: 0.08 }); },
  splash(size = 1) { const o = out(); if (!o) return; const t = AE.now; noise(t, 0.5 * size, o, { type: 'lowpass', f: 2200, f1: 300, gain: 0.25 * Math.min(1.5, size) }); for (let i = 0; i < 5; i++) osc('sine', R(600, 1200), t + i * 0.05, 0.08, o, { f1: R(200, 400), gain: 0.05 }); },
  roar() { const o = out(); if (!o) return; const t = AE.now; formantVoice(t, 90, 60, 1.3, [[400, 3], [800, 4]], 0.5); noise(t, 1.2, o, { type: 'lowpass', f: 600, gain: 0.15, attack: 0.1 }); },
  ogLaugh() { const o = out(); if (!o) return; for (let i = 0; i < 5; i++) formantVoice(AE.now + i * 0.16, 140 - i * 6, 120 - i * 6, 0.13, [[600, 4], [1000, 5]], 0.32); },
  ogHurt() { const o = out(); if (!o) return; formantVoice(AE.now, 160, 240, 0.35, [[500, 5], [1500, 6]], 0.3); },
  stomp() { const o = out(); if (!o) return; const t = AE.now; osc('square', 300, t, 0.1, o, { f1: 120, gain: 0.1 }); noise(t, 0.06, o, { type: 'lowpass', f: 900, gain: 0.1 }); },
  enemyHit() { const o = out(); if (!o) return; osc('square', 520, AE.now, 0.08, o, { f1: 260, gain: 0.07 }); },
  enemyDefeat() { const o = out(); if (!o) return; const t = AE.now; [660, 880, 1320].forEach((f, i) => osc('square', f, t + i * 0.05, 0.08, o, { gain: 0.05 })); this.pop(1.2); },
  fireworks() { const o = out(); if (!o) return; const t = AE.now; osc('sine', 300, t, 0.5, o, { f1: 1400, gain: 0.05 }); noise(t + 0.5, 0.6, o, { type: 'lowpass', f: 3000, f1: 300, gain: 0.2 }); for (let i = 0; i < 8; i++) noise(t + 0.55 + Math.random() * 0.6, 0.02, o, { type: 'highpass', f: 5000, gain: 0.06 }); },
  growl() { const o = out(); if (!o) return; const t = AE.now; osc('sawtooth', 70, t, 0.9, o, { f1: 45, gain: 0.12, attack: 0.1 }); const ctx = AE.ctx!; const l = ctx.createOscillator(), lg = ctx.createGain(); l.frequency.value = 9; lg.gain.value = 25; l.connect(lg); lg.connect(osc('sine', 90, t, 0.9, o, { gain: 0.1 }).o.frequency); l.start(t); l.stop(t + 1); },
  scratch() { const o = out(); if (!o) return; const t = AE.now; noise(t, 0.35, o, { f: 3000, f1: 300, q: 2, gain: 0.25 }); },
  chime() { const o = out(); if (!o) return; const t = AE.now; [1046, 1318, 1568, 2093].forEach((f, i) => osc('triangle', f, t + i * 0.08, 0.5, o, { gain: 0.07 })); },
  ui(kind: 'move' | 'ok' | 'back' = 'move') { const o = out(); if (!o) return; const t = AE.now; if (kind === 'move') osc('square', 880, t, 0.05, o, { gain: 0.04 }); else if (kind === 'ok') { osc('square', 660, t, 0.06, o, { gain: 0.05 }); osc('square', 990, t + 0.06, 0.09, o, { gain: 0.05 }); } else osc('square', 440, t, 0.08, o, { f1: 330, gain: 0.05 }); },
  whoosh() { const o = out(); if (!o) return; noise(AE.now, 0.9, o, { f: 300, f1: 2400, q: 0.6, gain: 0.14, attack: 0.3 }); },
  rumble(dur = 0.6) { const o = out(); if (!o) return; const t = AE.now; osc('sawtooth', 40, t, dur, o, { f1: 32, gain: 0.12, attack: 0.05 }); noise(t, dur, o, { type: 'lowpass', f: 180, gain: 0.12 }); },
  sparkle() { const o = out(); if (!o) return; const t = AE.now; for (let i = 0; i < 5; i++) osc('sine', R(2000, 4000), t + i * 0.05, 0.12, o, { gain: 0.03 }); },
  horn() { const o = out(); if (!o) return; const t = AE.now; for (const [a, d] of [[0, 0.22], [0.3, 0.6]]) for (const f of [233, 294]) osc('sawtooth', f, t + a, d, o, { gain: 0.07, attack: 0.02 }); },
  bell() { const o = out(); if (!o) return; const t = AE.now; for (let k = 0; k < 3; k++) { osc('sine', 1760, t + k * 0.18, 0.7, o, { gain: 0.08 }); osc('sine', 4400, t + k * 0.18, 0.3, o, { gain: 0.03 }); } },
  clunk() { const o = out(); if (!o) return; const t = AE.now; osc('square', 140, t, 0.12, o, { f1: 70, gain: 0.1 }); noise(t, 0.08, o, { type: 'lowpass', f: 600, gain: 0.15 }); },
  tweet() { const o = out(); if (!o) return; const t = AE.now; for (let i = 0; i < 3; i++) osc('sine', R(3000, 3600), t + i * 0.09, 0.06, o, { f1: R(2200, 2600), gain: 0.04 }); },
};
