/** Persistent settings + demo stats (localStorage, versioned). */
const KEY = 'simps-goose-v1';
export interface Settings { music: number; sfx: number; muted: boolean; bestDrops: number; plays: number; touch: 'auto' | 'on' | 'off' }
const DEF: Settings = { music: 0.7, sfx: 0.85, muted: false, bestDrops: 0, plays: 0, touch: 'auto' };
let cache: Settings | null = null;
export function settings(): Settings {
  if (cache) return cache;
  try { cache = { ...DEF, ...JSON.parse(localStorage.getItem(KEY) || '{}') }; } catch { cache = { ...DEF }; }
  return cache!;
}
export function saveSettings(patch: Partial<Settings> = {}) {
  cache = { ...settings(), ...patch };
  try { localStorage.setItem(KEY, JSON.stringify(cache)); } catch { /* private mode */ }
  listeners.forEach((f) => f(cache!));
}
const listeners: ((s: Settings) => void)[] = [];
export const onSettings = (f: (s: Settings) => void) => listeners.push(f);
