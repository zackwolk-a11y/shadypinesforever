// Renders every SFX and music theme to WAV via OfflineAudioContext (used by tests/export-assets.mjs).
import { AE, SFX_BUS } from '../audio/engine';
import { SFX } from '../audio/sfx';
import { MUSIC, Song } from '../audio/music';

function wav(buf: AudioBuffer): string {
  const ch = buf.numberOfChannels, len = buf.length, sr = buf.sampleRate;
  const out = new DataView(new ArrayBuffer(44 + len * ch * 2));
  const w = (o: number, s: string) => [...s].forEach((c, i) => out.setUint8(o + i, c.charCodeAt(0)));
  w(0, 'RIFF'); out.setUint32(4, 36 + len * ch * 2, true); w(8, 'WAVE'); w(12, 'fmt ');
  out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, ch, true); out.setUint32(24, sr, true);
  out.setUint32(28, sr * ch * 2, true); out.setUint16(32, ch * 2, true); out.setUint16(34, 16, true); w(36, 'data'); out.setUint32(40, len * ch * 2, true);
  let o = 44;
  for (let i = 0; i < len; i++) for (let c = 0; c < ch; c++) { const v = Math.max(-1, Math.min(1, buf.getChannelData(c)[i])); out.setInt16(o, v * 0x7fff, true); o += 2; }
  const bytes = new Uint8Array(out.buffer); let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}
async function render(seconds: number, f: () => number | void) {
  const sr = 22050;
  const ctx = new OfflineAudioContext(1, Math.ceil(sr * seconds), sr);
  const real = AE.ensure()!;
  const saved = { ctx: AE.ctx, master: AE.master, music: AE.music, sfx: AE.sfx, noise: AE.noise };
  AE.ctx = ctx as unknown as AudioContext;
  AE.master = ctx.createGain(); AE.master.gain.value = 0.9;
  AE.music = ctx.createGain(); AE.music.gain.value = 0.55 * 0.7; AE.sfx = ctx.createGain(); AE.sfx.gain.value = SFX_BUS * 0.85;
  AE.music.connect(AE.master); AE.sfx.connect(AE.master);
  const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -14; comp.ratio.value = 4;
  AE.master.connect(comp); comp.connect(ctx.destination);
  const nb = ctx.createBuffer(1, sr * 2, sr); nb.getChannelData(0).set(saved.noise.getChannelData(0).subarray(0, sr * 2)); AE.noise = nb;
  f();
  Object.assign(AE, saved);
  void real;
  return wav(await ctx.startRendering());
}
const SFX_LIST: [string, number, () => void][] = [
  ['honk', 0.6, () => SFX.honk()], ['honk_enormous', 1.2, () => SFX.honk(2.2)], ['footstep', 0.2, () => SFX.step()], ['jump', 0.3, () => SFX.jump()],
  ['land', 0.3, () => SFX.land()], ['wing_flap', 0.2, () => SFX.flap()], ['bottle_clink', 0.6, () => SFX.clink()], ['drink_slurp', 1, () => SFX.slurp()],
  ['swallow_gulp', 0.6, () => SFX.gulp()], ['syrup_pour', 1.2, () => SFX.pour()], ['carbonation_fizz', 1, () => SFX.fizz(0.8, 1)], ['bubble_blow', 0.4, () => SFX.bubble()],
  ['bubble_pop', 0.2, () => SFX.pop()], ['big_pop', 1.6, () => SFX.bigPop()], ['customer_oh', 0.5, () => SFX.oh()], ['customer_hey', 0.4, () => SFX.hey()],
  ['customer_laugh', 0.8, () => SFX.laugh()], ['customer_eek', 0.4, () => SFX.eek()], ['crowd_cheer', 1.2, () => SFX.cheer()], ['fountain_start', 2, () => SFX.fountainStart(1)],
  ['fountain_erupt', 2, () => SFX.fountainStart(2)], ['pressure_hiss', 1.2, () => SFX.hiss(1)], ['collect_drop', 0.4, () => SFX.collect()], ['collect_golden', 1, () => SFX.golden()],
  ['burp', 0.7, () => SFX.burp()], ['fizzy_dash', 0.6, () => SFX.dash()], ['foam_float', 0.7, () => SFX.foam()], ['cherry_shoot', 0.3, () => SFX.shoot()],
  ['box_crash', 0.6, () => SFX.crash()], ['valve', 0.9, () => SFX.valve()], ['door_bell', 1.2, () => SFX.door()], ['hurt', 0.7, () => SFX.hurt()],
  ['powerup', 0.6, () => SFX.powerup()], ['ui_move', 0.15, () => SFX.ui('move')], ['ui_ok', 0.25, () => SFX.ui('ok')], ['whoosh', 1.1, () => SFX.whoosh()], ['birds', 0.5, () => SFX.tweet()],
];
(window as unknown as { exportAudio: () => Promise<Record<string, string>> }).exportAudio = async () => {
  const out: Record<string, string> = {};
  for (const [n, d, f] of SFX_LIST) out['sfx/' + n + '.wav'] = await render(d, f);
  const song = async (name: string, s: 'title' | 'street' | 'store', bars: number, i: number) => {
    out['music/' + name + '.wav'] = await render(60 / (s === 'title' ? 112 : s === 'street' ? 104 : [128, 138, 150][i]) * 4 * bars + 1.2, () => { MUSIC.renderOffline(s, bars, i); });
  };
  await song('title_theme', 'title', 8, 1);
  await song('kelowna_street', 'street', 8, 0);
  await song('store_explore', 'store', 8, 0);
  await song('store_fountain_rumble', 'store', 8, 1);
  await song('store_bubble_trouble', 'store', 8, 2);
  for (const [n, s, i, bpm] of [['lab', 'lab', 1, 136], ['soda_dimension', 'dimension', 0, 116], ['carbonation_boss', 'boss', 1, 164], ['fake_ending_fanfare', 'fake', 0, 120], ['cafe', 'cafe', 0, 88], ['waterfront', 'waterfront', 0, 96], ['ogopogo_battle', 'ogopogo', 1, 154], ['true_ending_finale', 'finale', 0, 126]] as [string, Song, number, number][]) {
    out['music/' + n + '.wav'] = await render(60 / bpm * 4 * 4 + 1.2, () => { MUSIC.renderOffline(s, 4, i); });
  }
  const more: [string, number, () => void][] = [['syrup_pump', 0.4, () => SFX.pump()], ['mixer', 1.2, () => SFX.mixer(1)], ['soda_explosion', 1.6, () => SFX.explosion()], ['portal', 2, () => SFX.portal()], ['espresso', 1.8, () => SFX.espresso(1.5)], ['milk_froth', 1.4, () => SFX.froth(1.2)], ['grinder', 0.7, () => SFX.grind()], ['splash', 0.8, () => SFX.splash()], ['ogopogo_roar', 1.5, () => SFX.roar()], ['ogopogo_laugh', 1, () => SFX.ogLaugh()], ['ogopogo_hurt', 0.5, () => SFX.ogHurt()], ['stomp', 0.2, () => SFX.stomp()], ['enemy_defeat', 0.4, () => SFX.enemyDefeat()], ['fireworks', 1.4, () => SFX.fireworks()], ['stomach_growl', 1.1, () => SFX.growl()], ['record_scratch', 0.5, () => SFX.scratch()], ['chime', 0.8, () => SFX.chime()]];
  for (const [n, d, f] of more) out['sfx/' + n + '.wav'] = await render(d, f);
  out['music/to_be_continued_stinger.wav'] = await render(3, () => { MUSIC.stinger(); });
  return out;
};
(window as unknown as { __ready: boolean }).__ready = true;
