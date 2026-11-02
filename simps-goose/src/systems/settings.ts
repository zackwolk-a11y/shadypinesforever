/** Persistent settings + demo stats (localStorage, versioned). */
const KEY = 'simps-goose-v1';
export interface Settings { volV: number; music: number; sfx: number; muted: boolean; bestDrops: number; plays: number; touch: 'auto' | 'on' | 'off'; reduceFlash: boolean; reduceShake: boolean; highContrast: boolean }
const DEF: Settings = { volV: 2, music: 0.9, sfx: 0.5, muted: false, bestDrops: 0, plays: 0, touch: 'auto', reduceFlash: false, reduceShake: false, highContrast: false };
let cache: Settings | null = null;
export function settings(): Settings {
  if (cache) return cache;
  try { cache = { ...DEF, ...JSON.parse(localStorage.getItem(KEY) || '{}') }; } catch { cache = { ...DEF }; }
  // one-time move to the new default mix (music 9, sound effects 5)
  if (cache!.volV !== DEF.volV) { cache = { ...cache!, volV: DEF.volV, music: DEF.music, sfx: DEF.sfx }; try { localStorage.setItem(KEY, JSON.stringify(cache)); } catch { /* private mode */ } }
  return cache!;
}
export function saveSettings(patch: Partial<Settings> = {}) {
  cache = { ...settings(), ...patch };
  try { localStorage.setItem(KEY, JSON.stringify(cache)); } catch { /* private mode */ }
  listeners.forEach((f) => f(cache!));
}
const listeners: ((s: Settings) => void)[] = [];
export const onSettings = (f: (s: Settings) => void) => listeners.push(f);
