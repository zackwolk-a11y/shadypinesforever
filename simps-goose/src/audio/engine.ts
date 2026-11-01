/** Web Audio engine: master / music / sfx buses with persisted volumes. */
import { settings, onSettings } from '../systems/settings';

class Engine {
  ctx: AudioContext | null = null;
  master!: GainNode; music!: GainNode; sfx!: GainNode;
  noise!: AudioBuffer;
  comp!: DynamicsCompressorNode;
  ensure() {
    if (this.ctx) { if (this.ctx.state === 'suspended') this.ctx.resume(); return this.ctx; }
    const AC = (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext);
    if (!AC) return null;
    this.ctx = new AC();
    this.comp = this.ctx.createDynamicsCompressor();
    this.comp.threshold.value = -14; this.comp.ratio.value = 4;
    this.master = this.ctx.createGain();
    this.music = this.ctx.createGain(); this.sfx = this.ctx.createGain();
    this.music.connect(this.master); this.sfx.connect(this.master);
    this.master.connect(this.comp); this.comp.connect(this.ctx.destination);
    const len = this.ctx.sampleRate * 2;
    this.noise = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
    const d = this.noise.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    this.apply();
    onSettings(() => this.apply());
    return this.ctx;
  }
  apply() {
    if (!this.ctx) return;
    const s = settings();
    const t = this.ctx.currentTime;
    this.master.gain.setTargetAtTime(s.muted ? 0 : 0.9, t, 0.02);
    this.music.gain.setTargetAtTime(s.music * 0.55, t, 0.02);
    this.sfx.gain.setTargetAtTime(s.sfx, t, 0.02);
  }
  get now() { return this.ctx ? this.ctx.currentTime : 0; }
}
export const AE = new Engine();

// ---------- tiny synthesis helpers ----------
export function osc(type: OscillatorType, f0: number, t: number, dur: number, out: AudioNode, opts: { f1?: number; gain?: number; attack?: number; curve?: 'exp' | 'lin'; detune?: number } = {}) {
  const ctx = AE.ctx!;
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.type = type; o.frequency.setValueAtTime(f0, t);
  if (opts.detune) o.detune.value = opts.detune;
  if (opts.f1 !== undefined) {
    if (opts.curve === 'lin') o.frequency.linearRampToValueAtTime(opts.f1, t + dur);
    else o.frequency.exponentialRampToValueAtTime(Math.max(1, opts.f1), t + dur);
  }
  const a = opts.attack ?? 0.005, G = opts.gain ?? 0.3;
  g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(G, t + a); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g); g.connect(out); o.start(t); o.stop(t + dur + 0.05);
  return { o, g };
}
export function noise(t: number, dur: number, out: AudioNode, opts: { type?: BiquadFilterType; f?: number; f1?: number; q?: number; gain?: number; attack?: number } = {}) {
  const ctx = AE.ctx!;
  const s = ctx.createBufferSource(); s.buffer = AE.noise; s.loop = true;
  const f = ctx.createBiquadFilter(); f.type = opts.type ?? 'bandpass'; f.frequency.setValueAtTime(opts.f ?? 1000, t); f.Q.value = opts.q ?? 1;
  if (opts.f1) f.frequency.exponentialRampToValueAtTime(opts.f1, t + dur);
  const g = ctx.createGain(); const G = opts.gain ?? 0.3;
  g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(G, t + (opts.attack ?? 0.004)); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  s.connect(f); f.connect(g); g.connect(out);
  s.start(t, Math.random() * 1.5); s.stop(t + dur + 0.05);
  return { s, f, g };
}
export const mtof = (m: number) => 440 * Math.pow(2, (m - 69) / 12);
