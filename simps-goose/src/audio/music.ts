/**
 * Chiptune sequencer with layered intensity. All melodies are original.
 * Notation per bar: 16 sixteenth-note slots: "C5", "-" (hold), "." (rest).
 */
import { AE, mtof } from './engine';

const NOTE: Record<string, number> = { C: 0, 'C#': 1, Db: 1, D: 2, 'D#': 3, Eb: 3, E: 4, F: 5, 'F#': 6, Gb: 6, G: 7, 'G#': 8, Ab: 8, A: 9, 'A#': 10, Bb: 10, B: 11 };
const midi = (s: string) => { const m = s.match(/^([A-G][b#]?)(-?\d)$/)!; return NOTE[m[1]] + (+m[2] + 1) * 12; };
type Ev = { step: number; midi: number; len: number };
function parse(bars: string[]): Ev[] {
  const ev: Ev[] = [];
  bars.forEach((bar, bi) => {
    const tok = bar.trim().split(/\s+/);
    tok.forEach((t, i) => {
      if (t === '.' || t === '-') return;
      let len = 1; while (tok[i + len] === '-') len++;
      ev.push({ step: bi * 16 + i, midi: midi(t), len });
    });
  });
  return ev;
}

// I–vi–IV–V in F, then a lift.
const CHORDS = [['F2', [0, 4, 7]], ['D2', [0, 3, 7]], ['Bb1', [0, 4, 7]], ['C2', [0, 4, 7]], ['Bb1', [0, 4, 7]], ['C2', [0, 4, 7]], ['A1', [0, 3, 7]], ['D2', [0, 3, 7]]] as [string, number[]][];
const MEL = parse([
  'C5 . A4 . C5 . F5 - E5 . D5 . C5 - . .',
  'D5 . A4 . D5 . F5 - E5 . D5 . A4 - . .',
  'D5 . Bb4 . D5 . F5 - G5 . F5 . D5 - . .',
  'E5 . C5 . E5 . G5 - Bb5 - A5 . G5 . E5 .',
  'F5 - - . D5 . F5 . G5 - F5 . D5 - . .',
  'E5 - - . C5 . E5 . G5 - E5 . C5 - . .',
  'A5 - G5 . E5 . C5 . E5 . G5 . A5 - . .',
  'F5 . E5 . D5 . C5 . D5 - E5 - G5 - - .',
]);
const COUNTER = parse([
  'A4 - - - . . . . G4 - - - . . . .',
  'F4 - - - . . . . A4 - - - . . . .',
  'F4 - - - . . . . Bb4 - - - . . . .',
  'G4 - - - . . . . E4 - - - . . . .',
  'D4 - - - F4 - - - Bb4 - - - . . . .',
  'E4 - - - G4 - - - C5 - - - . . . .',
  'C5 - - - . . . . E4 - - - . . . .',
  'D4 - - - . . . . E4 - - - G4 - - -',
]);
const BASS_PAT = 'R . O . 5 . O . R . O . 5 . O R'.split(' ');

export type Song = 'title' | 'street' | 'store' | 'lab' | 'dimension' | 'boss' | 'fake' | 'cafe' | 'waterfront' | 'ogopogo' | 'finale' | 'warehouse' | 'none';
interface SongDef { bpm: (i: number) => number; chords: [string, number[]][]; mel: Ev[]; counter?: Ev[]; bass: string[]; lead: 'sq' | 'pluck' | 'tri' | 'sq50'; leadGain: number; drums: 'full' | 'light' | 'march'; arp: (i: number) => boolean; pad?: boolean; swing?: number }
const MAJ = [0, 4, 7], MIN = [0, 3, 7];
const SONGS: Partial<Record<Song, SongDef>> = {
  lab: { bpm: (i) => 128 + i * 8, chords: [['A1', MIN], ['F1', MAJ], ['G1', MAJ], ['E1', MAJ]], lead: 'sq', leadGain: 0.07, drums: 'full', arp: (i) => i >= 1, bass: 'R . R . O . R . 5 . R . O . 5 .'.split(' '),
    mel: parse(['A4 . C5 . E5 . A5 . G5 . E5 . C5 . D5 .', 'F4 . A4 . C5 . F5 . E5 . C5 . A4 . C5 .', 'G4 . B4 . D5 . G5 . F5 . D5 . B4 . D5 .', 'E5 - - . G#4 . B4 . E5 . D5 . B4 . G#4 .']) },
  dimension: { bpm: () => 116, chords: [['D2', MAJ], ['E2', MAJ], ['B1', MIN], ['A1', MAJ]], lead: 'tri', leadGain: 0.16, drums: 'light', arp: () => true, pad: true, bass: 'R . . . 5 . . . O . . . 5 . . .'.split(' '),
    mel: parse(['F#5 - - - A5 - - - E5 - - - D5 - - -', 'G#5 - - - B5 - - - A5 - G#5 - E5 - - -', 'F#5 - - - D5 - - - B4 - - - D5 - F#5 -', 'E5 - - - - - - - A4 - C#5 - E5 - - -']) },
  boss: { bpm: (i) => 156 + i * 8, chords: [['C2', MIN], ['Ab1', MAJ], ['Bb1', MAJ], ['G1', MAJ]], lead: 'sq', leadGain: 0.08, drums: 'full', arp: (i) => i >= 1, bass: 'R R O R 5 R O R R R O R 5 R O 5'.split(' '),
    mel: parse(['C5 . C5 . Eb5 . C5 . G5 - F5 . Eb5 . D5 .', 'C5 . C5 . Eb5 . Ab5 - G5 . F5 . Eb5 . C5 .', 'D5 . D5 . F5 . D5 . Bb5 - Ab5 . G5 . F5 .', 'G5 - - . F5 . D5 . B4 - - . D5 . G5 .']) },
  fake: { bpm: () => 120, chords: [['C2', MAJ], ['F2', MAJ], ['G2', MAJ], ['C2', MAJ]], lead: 'sq', leadGain: 0.08, drums: 'march', arp: () => false, pad: true, bass: 'R . . . 5 . . . O . . . 5 . . .'.split(' '),
    mel: parse(['C5 - E5 - G5 - - - C6 - - - G5 - - -', 'A5 - - - F5 - - - A5 - C6 - A5 - - -', 'B5 - - - G5 - - - D5 - G5 - B5 - - -', 'C6 - - - - - - - G5 - E5 - C5 - - -']) },
  cafe: { bpm: () => 88, chords: [['F2', [0, 4, 7, 11]], ['D2', [0, 3, 7, 10]], ['G1', [0, 3, 7, 10]], ['C2', [0, 4, 7, 10]]], lead: 'pluck', leadGain: 0.12, drums: 'light', arp: () => false, pad: true, swing: 0.18, bass: 'R . . . 5 . . . O . . . 5 . 3 .'.split(' '),
    mel: parse(['A4 - - C5 E5 - - - D5 - C5 - A4 - - -', 'F4 - - A4 C5 - - - D5 - - - . . . .', 'Bb4 - - D5 F5 - - - E5 - D5 - Bb4 - - -', 'E5 - - - G5 - - - F5 - E5 - C5 - - -']) },
  waterfront: { bpm: () => 96, chords: [['G1', MAJ], ['E1', MIN], ['C2', MAJ], ['D2', MAJ]], lead: 'pluck', leadGain: 0.13, drums: 'light', arp: () => false, pad: true, bass: 'R . . . 5 . . . O . . . 5 . . .'.split(' '),
    mel: parse(['B4 - - - D5 - - - G5 - - - F#5 - E5 -', 'E5 - - - B4 - - - G4 - - - B4 - - -', 'C5 - - - E5 - - - G5 - - - E5 - C5 -', 'D5 - - - F#5 - - - A5 - - - F#5 - - -']) },
  ogopogo: { bpm: (i) => 148 + i * 6, chords: [['E2', MIN], ['C2', MAJ], ['D2', MAJ], ['B1', MAJ]], lead: 'sq', leadGain: 0.08, drums: 'full', arp: (i) => i >= 1, pad: true, bass: 'R . O R 5 . O R R . O R 5 . O 5'.split(' '),
    mel: parse(['E5 . E5 . G5 . E5 . B5 - A5 . G5 . F#5 .', 'E5 . E5 . G5 . E5 . C6 - B5 . A5 . G5 .', 'D5 . F#5 . A5 . D6 . C6 . A5 . F#5 . D5 .', 'D#5 - - . F#5 . B4 . D#5 - F#5 - B5 - - .']) },
  warehouse: { bpm: (i) => 132 + i * 14, chords: [['C2', MAJ], ['A1', MIN], ['F1', MAJ], ['G1', MAJ]], lead: 'sq50', leadGain: 0.07, drums: 'full', arp: (i) => i >= 1, swing: 0.08, bass: 'R . R O 5 . R . R . R O 5 . 3 .'.split(' '),
    mel: parse(['C5 . E5 . G5 . E5 . C5 . D5 . E5 - - .', 'A4 . C5 . E5 . C5 . A4 . B4 . C5 - - .', 'F4 . A4 . C5 . F5 . E5 . D5 . C5 . A4 .', 'G4 . B4 . D5 . G5 . F5 . D5 . B4 - - .']) },
  finale: { bpm: () => 126, chords: [['D2', MAJ], ['G1', MAJ], ['A1', MAJ], ['D2', MAJ]], lead: 'sq', leadGain: 0.08, drums: 'full', arp: () => true, pad: true, bass: 'R . O . 5 . O . R . O . 5 . O R'.split(' '),
    mel: parse(['F#5 . A5 . D6 - - . A5 . F#5 . A5 - - .', 'G5 . B5 . D6 - - . B5 . G5 . B5 - - .', 'A5 . C#6 . E6 - - . C#6 . A5 . G5 . F#5 .', 'D6 - - - A5 - - - F#5 - - - D5 - - -']) },
};
class Music {
  song: Song = 'none';
  intensity = 0;
  private timer: number | null = null;
  private step = 0;
  private nextT = 0;
  private bpm = 120;
  private bus: GainNode | null = null;
  private wave25: PeriodicWave | null = null;

  private voice(type: 'sq' | 'tri' | 'pluck' | 'sq50', f: number, t: number, dur: number, gain: number) {
    const ctx = AE.ctx!, o = ctx.createOscillator(), g = ctx.createGain();
    if (type === 'sq') { o.setPeriodicWave(this.pulse()); } else if (type === 'sq50') o.type = 'square'; else o.type = 'triangle';
    o.frequency.value = f;
    const rel = type === 'pluck' ? dur * 0.6 : dur;
    g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(gain, t + 0.006);
    if (type === 'pluck') g.gain.exponentialRampToValueAtTime(0.0001, t + Math.max(0.12, rel));
    else { g.gain.setValueAtTime(gain * 0.8, t + dur * 0.7); g.gain.exponentialRampToValueAtTime(0.0001, t + dur + 0.04); }
    o.connect(g); g.connect(this.bus!); o.start(t); o.stop(t + dur + 0.2);
  }
  private pulse() {
    if (this.wave25) return this.wave25;
    const n = 32, re = new Float32Array(n), im = new Float32Array(n);
    for (let k = 1; k < n; k++) im[k] = (2 / (k * Math.PI)) * Math.sin(k * Math.PI * 0.25);
    this.wave25 = AE.ctx!.createPeriodicWave(re, im);
    return this.wave25;
  }
  private drum(kind: 'k' | 's' | 'h' | 'c', t: number, acc = 1) {
    const ctx = AE.ctx!;
    if (kind === 'k') {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.setValueAtTime(150, t); o.frequency.exponentialRampToValueAtTime(45, t + 0.12);
      g.gain.setValueAtTime(0.5 * acc, t); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
      o.connect(g); g.connect(this.bus!); o.start(t); o.stop(t + 0.2);
    } else {
      const s = ctx.createBufferSource(); s.buffer = AE.noise;
      const f = ctx.createBiquadFilter(); const g = ctx.createGain();
      const d = kind === 's' ? 0.13 : kind === 'c' ? 0.7 : 0.03;
      f.type = kind === 's' ? 'bandpass' : 'highpass'; f.frequency.value = kind === 's' ? 1800 : kind === 'c' ? 5000 : 7000;
      g.gain.setValueAtTime((kind === 's' ? 0.32 : kind === 'c' ? 0.16 : 0.09) * acc, t); g.gain.exponentialRampToValueAtTime(0.0001, t + d);
      s.connect(f); f.connect(g); g.connect(this.bus!); s.start(t, Math.random()); s.stop(t + d + 0.02);
    }
  }
  play(song: Song) {
    if (!AE.ensure()) return;
    if (SONGS[song]) { if (song === this.song) return; this.stop(); this.song = song; const ctx = AE.ctx!; this.bus = ctx.createGain(); this.bus.gain.value = 0; this.bus.connect(AE.music); this.bus.gain.linearRampToValueAtTime(1, ctx.currentTime + 0.4); this.step = 0; this.nextT = ctx.currentTime + 0.1; this.bpm = SONGS[song]!.bpm(this.intensity = 0); this.timer = window.setInterval(() => this.tick(), 25); return; }
    if (song === this.song) return;
    this.stop();
    this.song = song;
    if (song === 'none') return;
    const ctx = AE.ctx!;
    this.bus = ctx.createGain(); this.bus.gain.value = 0; this.bus.connect(AE.music);
    this.bus.gain.linearRampToValueAtTime(1, ctx.currentTime + 0.4);
    this.step = 0; this.nextT = ctx.currentTime + 0.1;
    this.bpm = song === 'title' ? 112 : song === 'street' ? 104 : 128;
    this.timer = window.setInterval(() => this.tick(), 25);
  }
  setIntensity(i: number) {
    this.intensity = i;
    const d = SONGS[this.song]; if (d) this.bpm = d.bpm(i);
    if (this.song === 'store') this.bpm = i >= 2 ? 150 : i === 1 ? 138 : 128;
  }
  stop(fade = 0.25) {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    if (this.bus && AE.ctx) { const b = this.bus; b.gain.cancelScheduledValues(AE.now); b.gain.setTargetAtTime(0, AE.now, fade / 3); setTimeout(() => b.disconnect(), fade * 1000 + 400); }
    this.bus = null;
    this.song = 'none';
  }
  /** Render a song offline (for asset export): schedules `bars` bars into the current AE.ctx. */
  renderOffline(song: Song, bars: number, intensity = 0) {
    this.song = song; this.intensity = intensity;
    this.bpm = SONGS[song] ? SONGS[song]!.bpm(intensity) : song === 'title' ? 112 : song === 'street' ? 104 : intensity >= 2 ? 150 : intensity === 1 ? 138 : 128;
    this.bus = AE.ctx!.createGain(); this.bus.connect(AE.music);
    const spb = 60 / this.bpm / 4;
    for (let st = 0; st < bars * 16; st++) this.schedule(st, 0.05 + st * spb, spb);
    this.song = song;
    return 0.05 + bars * 16 * spb + 1;
  }
  /** Abrupt stop (record scratch). */
  cut() { if (this.timer) clearInterval(this.timer); this.timer = null; if (this.bus) { this.bus.gain.cancelScheduledValues(AE.now); this.bus.gain.setValueAtTime(0, AE.now); const b = this.bus; setTimeout(() => b.disconnect(), 300); } this.bus = null; this.song = 'none'; }
  /** Freeze-frame "to be continued" stinger. */
  stinger() {
    if (!AE.ensure()) return;
    this.stop(0.05);
    const ctx = AE.ctx!;
    this.bus = ctx.createGain(); this.bus.connect(AE.music);
    const t = ctx.currentTime + 0.05;
    const seq = ['A4', 'G#4', 'G4', 'F#4', 'F4'];
    seq.forEach((n, i) => this.voice('pluck', mtof(midi(n)), t + i * 0.18, 0.25, 0.22));
    ['F3', 'A3', 'C4', 'E4'].forEach((n) => this.voice('tri', mtof(midi(n)), t + 1.0, 1.6, 0.14));
    ['F4', 'A4', 'C5', 'E5'].forEach((n, i) => this.voice('sq', mtof(midi(n)), t + 1.0 + i * 0.05, 1.5, 0.05));
    this.drum('c', t + 1.0);
  }
  private tick() {
    const ctx = AE.ctx!;
    const spb = 60 / this.bpm / 4;
    while (this.nextT < ctx.currentTime + 0.12) {
      this.schedule(this.step, this.nextT, spb);
      this.nextT += spb;
      this.step++;
    }
  }
  private scheduleDef(d: SongDef, step: number, t: number, spb: number) {
    const s16 = step % 16, pos = step % 64, bar = Math.floor(pos / 16), I = this.intensity;
    if (d.swing && s16 % 2 === 1) t += spb * d.swing;
    const [rootName, tri] = d.chords[bar];
    const root = midi(rootName);
    const bp = d.bass[s16];
    if (bp !== '.') { const m = bp === 'R' ? root : bp === 'O' ? root + 12 : bp === '3' ? root + tri[1] : root + 7; this.voice('tri', mtof(m + 12), t, spb * 1.6, 0.28); }
    if (d.pad && s16 === 0) for (const iv of tri.slice(0, 3)) this.voice('tri', mtof(root + 36 + iv), t, spb * 15, 0.035);
    for (const e of d.mel) if (e.step === pos) this.voice(d.lead, mtof(e.midi), t, spb * e.len * 0.92, d.leadGain);
    if (d.arp(I) && s16 % 2 === 0) { const ch = tri[(s16 / 2) % tri.length] + root + 36; this.voice('sq50', mtof(ch), t, spb * 0.8, 0.022); }
    if (d.drums === 'full') { if (s16 % 8 === 0 || (I >= 2 && s16 === 10)) this.drum('k', t); if (s16 === 4 || s16 === 12) this.drum('s', t); if (s16 % 2 === 0) this.drum('h', t, s16 % 4 === 0 ? 0.9 : 0.5); if (I >= 1 && s16 % 2 === 1) this.drum('h', t, 0.35); if (I >= 2 && pos === 0) this.drum('c', t); }
    else if (d.drums === 'light') { if (s16 === 0) this.drum('k', t, 0.6); if (s16 === 8) this.drum('s', t, 0.3); if (s16 % 4 === 2) this.drum('h', t, 0.4); }
    else { if (s16 % 4 === 0) this.drum('k', t, 0.8); if (s16 === 4 || s16 === 12 || s16 === 14) this.drum('s', t, 0.6); if (pos === 0) this.drum('c', t, 0.8); }
  }
  private schedule(step: number, t: number, spb: number) {
    const d = SONGS[this.song]; if (d) return this.scheduleDef(d, step, t, spb);
    const s16 = step % 16;
    const total = this.song === 'store' ? 128 : 64; // store: 8 bars, others: first 4 bars
    const pos = step % total;
    const bar = Math.floor(pos / 16);
    const [rootName, tri] = CHORDS[bar];
    const root = midi(rootName);
    const I = this.song === 'store' ? this.intensity : this.song === 'title' ? 1 : 0;

    // bass
    const bp = BASS_PAT[s16];
    if (bp !== '.') {
      const m = bp === 'R' ? root : bp === 'O' ? root + 12 : root + 7;
      if (this.song === 'street') { if (s16 % 4 === 0) this.voice('tri', mtof(m + 12), t, spb * 3, 0.22); }
      else this.voice('tri', mtof(m + 12), t, spb * 1.6, 0.3);
    }
    // melody
    for (const e of MEL) if (e.step === pos) {
      if (this.song === 'street') this.voice('pluck', mtof(e.midi), t, spb * e.len, 0.12);
      else this.voice(I >= 1 ? 'sq' : 'pluck', mtof(e.midi), t, spb * e.len * 0.9, I >= 1 ? 0.075 : 0.13);
    }
    if (I >= 1) for (const e of COUNTER) if (e.step === pos) this.voice('tri', mtof(e.midi), t, spb * e.len, 0.08);
    if (I >= 2 && s16 % 2 === 0) { const ch = tri[(s16 / 2) % 3] + root + 36; this.voice('sq50', mtof(ch), t, spb * 0.8, 0.025); }
    // drums
    if (this.song !== 'street' || s16 % 8 === 0) {
      if (s16 === 0 || s16 === 8 || (I >= 2 && s16 === 10)) this.drum('k', t);
      if (s16 === 4 || s16 === 12) this.drum('s', t, this.song === 'street' ? 0.4 : 1);
    }
    if (I >= 1 && s16 % 2 === 0) this.drum('h', t, s16 % 4 === 0 ? 1 : 0.6);
    if (I >= 2 && s16 % 2 === 1) this.drum('h', t, 0.4);
    if (I >= 2 && pos === 0) this.drum('c', t);
    if (this.song === 'street' && s16 % 4 === 2) this.drum('h', t, 0.5);
  }
}
export const MUSIC = new Music();
