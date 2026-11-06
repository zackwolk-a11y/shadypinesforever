// ============================================================================
// AudioSys — procedural synth band, adaptive sequencer, beat clock, SFX
// Everything is synthesised at runtime from WebAudio oscillators and noise.
// ============================================================================
const mtof = m => 440 * Math.pow(2, (m - 69) / 12);
const SCALES = {
  minor: [0, 2, 3, 5, 7, 8, 10], phrygian: [0, 1, 3, 5, 7, 8, 10], dorian: [0, 2, 3, 5, 7, 9, 10], mixo: [0, 2, 4, 5, 7, 9, 10],
  major: [0, 2, 4, 5, 7, 9, 11], harm: [0, 2, 3, 5, 7, 8, 11], blues: [0, 3, 5, 6, 7, 10, 12], whole: [0, 2, 4, 6, 8, 10, 12], locrian: [0, 1, 3, 5, 6, 8, 10]
};
const AudioSys = {
  ac: null, ok: false, musicVol: .7, sfxVol: .8, song: null, intensity: 1, targetIntensity: 1, muted: false,
  beatTimes: [], curBeat: 0, virtualT0: performance.now() / 1000,
  init() {
    try {
      const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
      const ac = this.ac = new AC();
      this.master = ac.createGain(); this.master.gain.value = .9;
      const comp = ac.createDynamicsCompressor(); comp.threshold.value = -14; comp.ratio.value = 4; comp.attack.value = .004; comp.release.value = .15;
      this.master.connect(comp); comp.connect(ac.destination);
      this.music = ac.createGain(); this.music.connect(this.master);
      this.sfx = ac.createGain(); this.sfx.connect(this.master);
      this.applyVolumes();
      // noise buffer
      const nb = ac.createBuffer(1, ac.sampleRate * 2, ac.sampleRate), d = nb.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
      this.noise = nb;
      this.distCurve = this.makeCurve(260); this.softCurve = this.makeCurve(18);
      // guitar buses (double tracked L/R)
      this.gtr = [-.65, .65].map(p => {
        const pre = ac.createGain(); pre.gain.value = 2.4;
        const ws = ac.createWaveShaper(); ws.curve = this.distCurve; ws.oversample = '2x';
        const hp = ac.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 90;
        const lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 4200; lp.Q.value = .8;
        const mid = ac.createBiquadFilter(); mid.type = 'peaking'; mid.frequency.value = 700; mid.gain.value = -5; mid.Q.value = 1;
        const out = ac.createGain(); out.gain.value = .085;
        const pan = ac.createStereoPanner ? ac.createStereoPanner() : null;
        pre.connect(ws); ws.connect(hp); hp.connect(mid); mid.connect(lp); lp.connect(out);
        if (pan) { pan.pan.value = p; out.connect(pan); pan.connect(this.music); } else out.connect(this.music);
        return pre;
      });
      // lead bus with delay
      const lpre = ac.createGain(); lpre.gain.value = 3;
      const lws = ac.createWaveShaper(); lws.curve = this.distCurve;
      const llp = ac.createBiquadFilter(); llp.type = 'lowpass'; llp.frequency.value = 3600;
      const lout = ac.createGain(); lout.gain.value = .075;
      const dl = ac.createDelay(1); dl.delayTime.value = .33; const fb = ac.createGain(); fb.gain.value = .32;
      lpre.connect(lws); lws.connect(llp); llp.connect(lout); lout.connect(this.music); lout.connect(dl); dl.connect(fb); fb.connect(dl); dl.connect(this.music);
      this.lead = lpre; this.leadDelay = dl;
      // bass bus
      const bws = ac.createWaveShaper(); bws.curve = this.softCurve; const blp = ac.createBiquadFilter(); blp.type = 'lowpass'; blp.frequency.value = 900;
      const bout = ac.createGain(); bout.gain.value = .32; bws.connect(blp); blp.connect(bout); bout.connect(this.music); this.bass = bws;
      // drum bus
      const dc = ac.createDynamicsCompressor(); dc.threshold.value = -10; dc.ratio.value = 6; const dout = ac.createGain(); dout.gain.value = .9;
      dc.connect(dout); dout.connect(this.music); this.drums = dc;
      // clean bus (organ / kazoo / pads)
      const cl = ac.createGain(); cl.gain.value = .5; cl.connect(this.music); this.clean = cl;
      this.ok = true;
      setInterval(() => this.schedule(), 25);
    } catch (e) { console.warn('audio init failed', e); }
  },
  makeCurve(k) { const n = 2048, c = new Float32Array(n); for (let i = 0; i < n; i++) { const x = i * 2 / n - 1; c[i] = (1 + k) * x / (1 + k * Math.abs(x)); } return c; },
  unlock() { if (!this.ac) this.init(); if (this.ac && this.ac.state !== 'running') { this.ac.resume().then(() => { this.resync(); }); } },
  running() { return this.ac && this.ac.state === 'running'; },
  now() { return this.running() ? this.ac.currentTime : G.t; },
  resync() { if (this.song) { this.nextTime = this.now() + .08; this.beatTimes = []; } },
  applyVolumes() { if (!this.music) return; this.music.gain.value = this.musicVol * .9; this.sfx.gain.value = this.sfxVol; },

  // -------------------------------------------------------------- instruments
  env(g, t, a, peak, dur, rel) { g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(peak, t + a); g.gain.setValueAtTime(peak, t + Math.max(a, dur)); g.gain.exponentialRampToValueAtTime(.0001, t + Math.max(a, dur) + rel); },
  osc(type, f, t, end, dest, detune = 0) { const o = this.ac.createOscillator(); o.type = type; o.frequency.value = f; o.detune.value = detune; o.connect(dest); o.start(t); o.stop(end + .05); return o; },
  guitar(t, midi, dur, mute, power = true, vol = 1) {
    const ac = this.ac, notes = power ? [midi, midi + 7, midi + 12] : [midi];
    this.gtr.forEach((bus, side) => {
      const tt = t + side * .006;
      const lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = mute ? 700 : 5000;
      const g = ac.createGain(); lp.connect(g); g.connect(bus);
      this.env(g, tt, .004, (mute ? .55 : .42) * vol, mute ? .04 : dur, mute ? .06 : .09);
      for (const n of notes) { this.osc('sawtooth', mtof(n), tt, tt + dur + .15, lp, side ? 9 : -9); }
    });
  },
  bassNote(t, midi, dur, vol = 1) {
    const g = this.ac.createGain(); g.connect(this.bass); this.env(g, t, .005, .9 * vol, dur * .85, .06);
    this.osc('sawtooth', mtof(midi), t, t + dur + .1, g); this.osc('square', mtof(midi - 12), t, t + dur + .1, g);
  },
  leadNote(t, midi, dur, bend = 0, vol = 1) {
    const g = this.ac.createGain(); g.connect(this.lead); this.env(g, t, .01, .5 * vol, dur, .12);
    const o = this.osc('sawtooth', mtof(midi), t, t + dur + .2, g);
    const o2 = this.osc('square', mtof(midi), t, t + dur + .2, g, 6);
    if (bend) { o.frequency.setValueAtTime(mtof(midi - bend), t); o.frequency.linearRampToValueAtTime(mtof(midi), t + Math.min(.12, dur)); }
    const lfo = this.ac.createOscillator(), lg = this.ac.createGain(); lfo.frequency.value = 6; lg.gain.value = 9; lfo.connect(lg); lg.connect(o.detune); lg.connect(o2.detune); lfo.start(t + .1); lfo.stop(t + dur + .2);
  },
  organ(t, midis, dur, vol = 1) {
    const g = this.ac.createGain(); g.connect(this.clean); this.env(g, t, .01, .12 * vol, dur, .08);
    for (const m of midis) { this.osc('square', mtof(m), t, t + dur + .1, g); this.osc('sine', mtof(m + 12), t, t + dur + .1, g); }
  },
  kazoo(t, midi, dur, vol = 1) {
    const bp = this.ac.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = 1300; bp.Q.value = 2.5;
    const g = this.ac.createGain(); bp.connect(g); g.connect(this.clean); this.env(g, t, .02, .5 * vol, dur, .05);
    const o = this.osc('sawtooth', mtof(midi), t, t + dur + .1, bp);
    const lfo = this.ac.createOscillator(), lg = this.ac.createGain(); lfo.frequency.value = 7; lg.gain.value = 25; lfo.connect(lg); lg.connect(o.detune); lfo.start(t); lfo.stop(t + dur + .1);
  },
  pad(t, midis, dur, vol = 1) {
    const lp = this.ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.setValueAtTime(400, t); lp.frequency.linearRampToValueAtTime(2200, t + dur * .6); lp.frequency.linearRampToValueAtTime(500, t + dur);
    const g = this.ac.createGain(); lp.connect(g); g.connect(this.clean); this.env(g, t, dur * .3, .1 * vol, dur * .5, dur * .3);
    for (const m of midis) { this.osc('sawtooth', mtof(m), t, t + dur * 1.2, lp, -12); this.osc('sawtooth', mtof(m), t, t + dur * 1.2, lp, 12); }
  },
  noiseHit(t, dest, type, freq, q, peak, dur, rate = 1) {
    const s = this.ac.createBufferSource(); s.buffer = this.noise; s.playbackRate.value = rate;
    const f = this.ac.createBiquadFilter(); f.type = type; f.frequency.value = freq; f.Q.value = q;
    const g = this.ac.createGain(); s.connect(f); f.connect(g); g.connect(dest);
    g.gain.setValueAtTime(peak, t); g.gain.exponentialRampToValueAtTime(.0001, t + dur);
    s.start(t, Math.random()); s.stop(t + dur + .02); return f;
  },
  kick(t, vol = 1) {
    const g = this.ac.createGain(); g.connect(this.drums); g.gain.setValueAtTime(1.3 * vol, t); g.gain.exponentialRampToValueAtTime(.001, t + .28);
    const o = this.osc('sine', 150, t, t + .3, g); o.frequency.setValueAtTime(160, t); o.frequency.exponentialRampToValueAtTime(42, t + .12);
    this.noiseHit(t, this.drums, 'highpass', 3000, .7, .25 * vol, .015);
  },
  snare(t, vol = 1) {
    this.noiseHit(t, this.drums, 'bandpass', 1900, .6, .75 * vol, .17);
    const g = this.ac.createGain(); g.connect(this.drums); g.gain.setValueAtTime(.45 * vol, t); g.gain.exponentialRampToValueAtTime(.001, t + .09);
    const o = this.osc('triangle', 200, t, t + .1, g); o.frequency.exponentialRampToValueAtTime(140, t + .08);
  },
  hat(t, open, vol = 1) { this.noiseHit(t, this.drums, 'highpass', 7800, .5, .22 * vol, open ? .2 : .035); },
  crash(t, vol = 1) { this.noiseHit(t, this.drums, 'highpass', 4500, .4, .45 * vol, 1.3, .9); },
  tom(t, f, vol = 1) { const g = this.ac.createGain(); g.connect(this.drums); g.gain.setValueAtTime(.9 * vol, t); g.gain.exponentialRampToValueAtTime(.001, t + .25); const o = this.osc('sine', f, t, t + .26, g); o.frequency.exponentialRampToValueAtTime(f * .55, t + .2); },
  cowbell(t, vol = 1) { const bp = this.ac.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = 800; bp.Q.value = 3; const g = this.ac.createGain(); bp.connect(g); g.connect(this.drums); g.gain.setValueAtTime(.35 * vol, t); g.gain.exponentialRampToValueAtTime(.001, t + .18); this.osc('square', 560, t, t + .2, bp); this.osc('square', 845, t, t + .2, bp); },
  clang(t, vol = 1) {
    const bp = this.ac.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = 2400; bp.Q.value = 4;
    const g = this.ac.createGain(); bp.connect(g); g.connect(this.drums); g.gain.setValueAtTime(.5 * vol, t); g.gain.exponentialRampToValueAtTime(.001, t + .35);
    this.osc('square', 317, t, t + .36, bp); this.osc('square', 488, t, t + .36, bp); this.osc('square', 1213, t, t + .36, bp);
  },

  // -------------------------------------------------------------- music sequencer
  play(id, force) {
    const song = SONGS[id]; if (!song) return;
    if (this.song && this.song.id === id && !force) return;
    this.song = song; this.partQ = []; this.part = null; this.step = 0; this.bar = 0;
    this.nextTime = this.now() + .1; this.beatTimes = []; this.songBeat = 0;
    this.lastMood = -1;
  },
  stop() { this.song = null; },
  setIntensity(n) { this.targetIntensity = n; },
  arrangement() { const s = this.song, i = this.intensity; if (i >= 3) return this.bossPhase >= 3 ? ['F', 'F', 'D', 'F', 'E'] : this.bossPhase === 2 ? ['F', 'E', 'F', 'C', 'D'] : s.boss; return i >= 2 ? s.combat : i <= 0 ? s.calm : s.explore; },
  setBossPhase(n) { if (this.bossPhase !== n) { this.bossPhase = n; this.lastMood = -1; } },
  nextPart() {
    if (this.intensity !== this.targetIntensity || this.lastMood !== this.intensity) {
      this.intensity = this.targetIntensity; this.lastMood = this.intensity; this.arrIdx = 0;
    }
    const arr = this.arrangement();
    const name = arr[this.arrIdx % arr.length]; this.arrIdx++;
    if (this.arrIdx >= arr.length) this.arrIdx = this.song.loopFrom || 0;
    this.part = this.song.parts[name]; this.partName = name; this.step = 0;
  },
  schedule() {
    const s = this.song; if (!s) return; if (this.nextTime === undefined) this.nextTime = this.now();
    const now = this.now();
    if (this.nextTime < now - .5) this.nextTime = now + .05; // tab was asleep
    while (this.nextTime < now + .13) {
      if (!this.part || this.step >= this.part.len) this.nextPart();
      const p = this.part, st = this.step, t = this.nextTime;
      const bpm = s.bpm * (p.tempo || 1), stepDur = 60 / bpm / (s.div || 4);
      if (st % (s.div || 4) === 0) { this.beatTimes.push({ t, n: this.songBeat++, bpm }); if (this.beatTimes.length > 16) this.beatTimes.shift(); }
      if (this.running() && !this.muted && this.musicVol > 0) this.playStep(p, st, t, stepDur);
      this.step++; this.nextTime += stepDur * (s.swing && st % 2 === 0 ? 1 + s.swing : s.swing && st % 2 ? 1 - s.swing : 1);
    }
  },
  playStep(p, st, t, sd) {
    const I = this.intensity;
    const ev = p.ev[st]; if (!ev) return;
    if (ev.k) this.kick(t, ev.k); if (ev.s) this.snare(t, ev.s); if (ev.h) this.hat(t, ev.h > 1); if (ev.c) this.crash(t);
    if (ev.cl) this.clang(t); if (ev.tm) this.tom(t, ev.tm);
    if (I >= 2 && p.dk && st % 2 === 1) this.kick(t, .55);
    if (ev.g && I >= 1) this.guitar(t, ev.g[0], ev.g[1] * sd, ev.g[2], ev.g[3] !== false);
    if (ev.b) this.bassNote(t, ev.b[0], ev.b[1] * sd);
    if (ev.l && (I >= 1 || p.leadAlways)) this.leadNote(t, ev.l[0], ev.l[1] * sd, ev.l[2], ev.l[3] || 1);
    if (ev.cb) this.cowbell(t, ev.cb);
    if (ev.o) this.organ(t, ev.o[0], ev.o[1] * sd);
    if (ev.z) this.kazoo(t, ev.z[0], ev.z[1] * sd);
    if (ev.p) this.pad(t, ev.p[0], ev.p[1] * sd);
  },
  // beat clock for rhythm gameplay: returns {beat, phase, bpm}
  beat() {
    const now = this.now(), bt = this.beatTimes;
    for (let i = bt.length - 1; i >= 0; i--) if (bt[i].t <= now) { const len = 60 / bt[i].bpm; return { beat: bt[i].n, phase: clamp((now - bt[i].t) / len, 0, .999), bpm: bt[i].bpm }; }
    return { beat: 0, phase: (now * 2) % 1, bpm: 120 };
  },
  onBeatWindow(win = .16) { const b = this.beat(); return b.phase < win || b.phase > 1 - win * .6; },

  // -------------------------------------------------------------- SFX
  sfxOn() { return this.running() && this.sfxVol > 0; },
  play_sfx(name, o = {}) {
    if (!this.sfxOn()) return; const f = SFX[name]; if (f) try { f.call(this, this.ac.currentTime, o); } catch (e) { }
  },
  sweep(t, type, f0, f1, dur, vol, dest) {
    const g = this.ac.createGain(); g.connect(dest || this.sfx); g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(.001, t + dur);
    const o = this.osc(type, f0, t, t + dur, g); o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + dur); return o;
  },
  engine: null,
  setEngine(on, rpm = .5) {
    if (!this.sfxOn()) return;
    if (on && !this.engine) {
      const ac = this.ac, g = ac.createGain(); g.gain.value = 0; const ws = ac.createWaveShaper(); ws.curve = this.distCurve;
      const lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 900; ws.connect(lp); lp.connect(g); g.connect(this.sfx);
      const o1 = ac.createOscillator(); o1.type = 'sawtooth'; const o2 = ac.createOscillator(); o2.type = 'square';
      const lfo = ac.createOscillator(); lfo.type = 'square'; const lg = ac.createGain(); lfo.connect(lg); lg.connect(g.gain);
      const pre = ac.createGain(); pre.gain.value = .5; o1.connect(pre); o2.connect(pre); pre.connect(ws);
      o1.start(); o2.start(); lfo.start(); this.engine = { g, o1, o2, lfo, lg, lp };
    }
    if (this.engine) {
      const e = this.engine, t = this.ac.currentTime;
      if (!on) { e.g.gain.setTargetAtTime(0, t, .1); const ee = e; setTimeout(() => { try { ee.o1.stop(); ee.o2.stop(); ee.lfo.stop(); } catch (x) { } }, 400); this.engine = null; return; }
      const f = 38 + rpm * 70; e.o1.frequency.setTargetAtTime(f, t, .05); e.o2.frequency.setTargetAtTime(f * .5, t, .05);
      e.lfo.frequency.setTargetAtTime(f / 2.2, t, .05); e.lg.gain.value = .04; e.g.gain.setTargetAtTime(.09, t, .05); e.lp.frequency.setTargetAtTime(500 + rpm * 1400, t, .05);
    }
  }
};
const SFX = {
  jump(t) { this.sweep(t, 'square', 220, 520, .12, .12); },
  land(t) { this.sweep(t, 'sine', 140, 50, .1, .3); this.noiseHit(t, this.sfx, 'lowpass', 600, 1, .2, .06); },
  whip(t) { this.noiseHit(t, this.sfx, 'bandpass', 2400, 2, .5, .12, 1.4); this.sweep(t, 'sawtooth', 900, 200, .1, .06); },
  slurp(t) { this.sweep(t, 'sine', 300, 900, .15, .2); this.sweep(t + .05, 'sine', 500, 1200, .1, .12); },
  spit(t) { this.noiseHit(t, this.sfx, 'lowpass', 1200, 4, .5, .14); this.sweep(t, 'sine', 600, 120, .12, .25); },
  splat(t) { this.noiseHit(t, this.sfx, 'lowpass', 800, 6, .6, .18, .7); this.sweep(t, 'sine', 300, 60, .14, .2); },
  bash(t) { this.sweep(t, 'square', 180, 60, .15, .2); this.noiseHit(t, this.sfx, 'bandpass', 3000, 3, .3, .1); this.clangS(t); },
  clangS(t) { const g = this.ac.createGain(); g.connect(this.sfx); g.gain.setValueAtTime(.12, t); g.gain.exponentialRampToValueAtTime(.001, t + .3); this.osc('square', 523, t, t + .3, g); this.osc('square', 791, t, t + .3, g); },
  dash(t) { this.noiseHit(t, this.sfx, 'bandpass', 900, 1, .6, .3, .6); this.sweep(t, 'sawtooth', 80, 220, .25, .12); },
  scream(t, o) {
    const p = o.power || 1, d = .5 + p * .6, ac = this.ac;
    const ws = ac.createWaveShaper(); ws.curve = this.distCurve; const g = ac.createGain(); ws.connect(g); g.connect(this.sfx);
    g.gain.setValueAtTime(.0, t); g.gain.linearRampToValueAtTime(.32, t + .04); g.gain.exponentialRampToValueAtTime(.001, t + d);
    const pre = ac.createGain(); pre.gain.value = .6; pre.connect(ws);
    const o1 = this.osc('sawtooth', 190, t, t + d, pre); o1.frequency.linearRampToValueAtTime(95, t + d);
    const o2 = this.osc('sawtooth', 197, t, t + d, pre); o2.frequency.linearRampToValueAtTime(70, t + d);
    const f = this.noiseHit(t, this.sfx, 'bandpass', 900, 3, .7, d, .8); f.frequency.linearRampToValueAtTime(2600, t + d * .3); f.frequency.linearRampToValueAtTime(500, t + d);
  },
  charge(t) { this.sweep(t, 'sawtooth', 100, 400, .4, .05); },
  hurt(t) { this.sweep(t, 'square', 400, 90, .25, .2); this.noiseHit(t, this.sfx, 'lowpass', 1500, 1, .3, .1); },
  enemyHit(t) { this.sweep(t, 'square', 700, 200, .08, .14); },
  squish(t) { this.noiseHit(t, this.sfx, 'lowpass', 700, 8, .7, .25, .5); this.sweep(t, 'sine', 500, 40, .25, .3); },
  pop(t) { this.sweep(t, 'sine', 900, 1800, .06, .2); },
  note(t) { [0, 4, 7].forEach((n, i) => { const g = this.ac.createGain(); g.connect(this.sfx); this.env(g, t + i * .04, .003, .09, .03, .08); this.osc('square', mtof(84 + n), t + i * .04, t + i * .04 + .12, g); }); },
  shard(t) { [0, 7, 12, 16, 19, 24].forEach((n, i) => { const g = this.ac.createGain(); g.connect(this.sfx); this.env(g, t + i * .06, .003, .1, .05, .2); this.osc('triangle', mtof(76 + n), t + i * .06, t + i * .06 + .3, g); }); },
  checkpoint(t) { this.guitar(t, 40, .5, false); this.guitar(t + .25, 47, .7, false); this.crash(t); },
  power(t) { [0, 3, 7, 10, 12, 15, 19, 24].forEach((n, i) => this.leadNote(t + i * .07, 64 + n, .1, 0, .7)); },
  explode(t) { this.noiseHit(t, this.sfx, 'lowpass', 1200, .5, 1, .9, .5); this.sweep(t, 'sine', 120, 30, .6, .6); },
  boing(t) { const o = this.sweep(t, 'sine', 200, 200, .4, .3); o.frequency.setValueAtTime(180, t); o.frequency.linearRampToValueAtTime(700, t + .1); o.frequency.linearRampToValueAtTime(300, t + .4); },
  honk(t) { this.kazoo(t, 62, .25, 1.4); },
  moo(t) { const g = this.ac.createGain(); g.connect(this.sfx); this.env(g, t, .08, .35, .6, .2); const bp = this.ac.createBiquadFilter(); bp.type = 'lowpass'; bp.frequency.value = 900; bp.connect(g); const o = this.osc('sawtooth', 110, t, t + .9, bp); o.frequency.linearRampToValueAtTime(140, t + .2); o.frequency.linearRampToValueAtTime(95, t + .85); },
  oink(t, o) { const p = o.pitch || 1; for (let i = 0; i < 2; i++) { const s = this.sweep(t + i * .13, 'sawtooth', 420 * p, 260 * p, .1, .14); } this.noiseHit(t, this.sfx, 'bandpass', 1200 * p, 3, .3, .2); },
  howl(t) { const g = this.ac.createGain(); g.connect(this.sfx); this.env(g, t, .2, .25, 1.2, .4); const o = this.osc('sawtooth', 300, t, t + 1.8, g); o.frequency.linearRampToValueAtTime(620, t + .4); o.frequency.linearRampToValueAtTime(540, t + 1.2); o.frequency.linearRampToValueAtTime(300, t + 1.7); const o2 = this.osc('sine', 600, t, t + 1.8, g); o2.frequency.linearRampToValueAtTime(1240, t + .4); o2.frequency.linearRampToValueAtTime(600, t + 1.7); },
  growl(t) { this.noiseHit(t, this.sfx, 'lowpass', 400, 4, .7, .5, .4); this.sweep(t, 'sawtooth', 90, 60, .5, .2); },
  rev(t) { this.sweep(t, 'sawtooth', 60, 220, .6, .2); this.sweep(t, 'square', 30, 110, .6, .15); },
  flap(t) { this.noiseHit(t, this.sfx, 'bandpass', 500, 1.5, .5, .15, .6); },
  gloop(t) { const o = this.sweep(t, 'sine', 120, 400, .2, .4); this.sweep(t + .1, 'sine', 200, 70, .2, .3); },
  menu(t) { this.sweep(t, 'square', 660, 660, .04, .08); },
  select(t) { this.sweep(t, 'square', 440, 880, .1, .12); this.sweep(t + .05, 'square', 660, 1320, .1, .08); },
  back(t) { this.sweep(t, 'square', 500, 250, .1, .1); },
  door(t) { this.sweep(t, 'sawtooth', 70, 140, .5, .2); this.noiseHit(t, this.sfx, 'lowpass', 400, 2, .4, .5); },
  switch(t) { this.sweep(t, 'square', 1200, 600, .05, .15); this.sweep(t + .06, 'square', 800, 1600, .05, .12); },
  break(t) { this.noiseHit(t, this.sfx, 'bandpass', 1500, 1, .8, .3, .8); this.sweep(t, 'square', 200, 50, .2, .2); },
  cheer(t) { for (let i = 0; i < 8; i++) this.noiseHit(t + i * .09, this.sfx, 'bandpass', 900 + Math.random() * 1600, 2, .25, .4, .8 + Math.random() * .4); },
  riff(t) { [40, 40, 43, 45, 40, 47, 46, 45].forEach((n, i) => this.guitar(t + i * .11, n, .1, i % 3 !== 1)); this.kick(t); this.crash(t + .77); },
  stinger(t) { this.guitar(t, 40, 1.2, false); this.crash(t); this.kick(t); this.snare(t + .02); },
  headbang(t, o) { const n = [40, 43, 45, 47, 50][o.combo % 5 | 0]; this.guitar(t, n, .18, false); this.kick(t, .8); },
  miss(t) { this.sweep(t, 'sawtooth', 200, 120, .2, .1); },
  zap(t) { this.sweep(t, 'sawtooth', 1800, 200, .15, .1); this.noiseHit(t, this.sfx, 'highpass', 4000, 1, .2, .1); },
  laser(t) { this.sweep(t, 'square', 1400, 300, .2, .1); },
  throw(t) { this.noiseHit(t, this.sfx, 'bandpass', 1800, 4, .3, .1, 1.6); },
  rumble(t) { this.noiseHit(t, this.sfx, 'lowpass', 160, 1, 1, 1.2, .3); },
  bite(t) { this.noiseHit(t, this.sfx, 'bandpass', 1100, 5, .6, .08); this.sweep(t, 'square', 300, 100, .08, .15); },
  transform(t) { for (let i = 0; i < 10; i++) this.sweep(t + i * .05, 'square', 200 + i * 80, 400 + i * 120, .06, .07); this.sweep(t + .5, 'sawtooth', 80, 40, .5, .25); },
  splash(t) { this.noiseHit(t, this.sfx, 'lowpass', 2000, 1, .6, .4, .7); },
  coaster(t) { this.noiseHit(t, this.sfx, 'lowpass', 300, 2, .3, .2); },
  text(t) { this.sweep(t, 'square', 520 + Math.random() * 120, 520, .02, .03); },
  bossDie(t) { for (let i = 0; i < 6; i++) { this.noiseHit(t + i * .18, this.sfx, 'lowpass', 900, .5, .9, .6, .5); this.sweep(t + i * .18, 'sine', 140, 30, .4, .5); } this.crash(t + 1.1); },
  ticket(t) { this.sweep(t, 'triangle', 1500, 1500, .05, .1); }
};
