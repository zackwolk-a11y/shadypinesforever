/**
 * Persistent progress (localStorage, versioned). Kept separate from settings
 * ('simps-goose-v1'), so saves from the vertical slice keep working.
 */
export type StageId = 'store' | 'lab' | 'dimension' | 'carb' | 'cafe' | 'waterfront' | 'ogopogo';
export const STAGES: { id: StageId; scene: string; level: 1 | 2 | 3; name: string }[] = [
  { id: 'store', scene: 'Intro', level: 1, name: 'BUBBLE TROUBLE' },
  { id: 'lab', scene: 'Lab', level: 2, name: "THE HONKIN' SODA LAB" },
  { id: 'dimension', scene: 'Dimension', level: 2, name: 'THE SODA DIMENSION' },
  { id: 'carb', scene: 'BossCarb', level: 2, name: 'CARBONATION CATASTROPHE' },
  { id: 'cafe', scene: 'Cafe', level: 3, name: 'ONE LAST SIP: THE CAFE' },
  { id: 'waterfront', scene: 'Waterfront', level: 3, name: 'THE WATERFRONT' },
  { id: 'ogopogo', scene: 'Ogopogo', level: 3, name: 'OGOPOGO!' },
];
export type MixQuality = 'perfect' | 'good' | 'over';
export interface SaveData {
  v: 2;
  unlocked: StageId[];
  completed: StageId[];
  bestScore: number; lastScore: number; bestTime: number;
  flavors: string[];
  recipes: Record<string, { quality: MixQuality; count: number; best: number }>;
  cards: string[];
  collected: string[];
  achievements: string[];
  coffee: string | null;
  coffees: string[];
  fakeEndingSeen: boolean; trueEnding: boolean;
  checkpoint: { stage: StageId; x: number; y: number } | null;
  run: { score: number; hearts: number; time: number; coffee: string | null } | null;
}
const KEY = 'simps-goose-save-v2';
const fresh = (): SaveData => ({ v: 2, unlocked: ['store'], completed: [], bestScore: 0, lastScore: 0, bestTime: 0, flavors: [], recipes: {}, cards: [], collected: [], achievements: [], coffee: null, coffees: [], fakeEndingSeen: false, trueEnding: false, checkpoint: null, run: null });
let cache: SaveData | null = null;
export function save(): SaveData {
  if (cache) return cache;
  try { const raw = JSON.parse(localStorage.getItem(KEY) || 'null'); cache = raw && raw.v === 2 ? { ...fresh(), ...raw } : fresh(); } catch { cache = fresh(); }
  return cache!;
}
export function persist() { try { localStorage.setItem(KEY, JSON.stringify(save())); } catch { /* private mode */ } }
export function update(f: (s: SaveData) => void) { f(save()); persist(); }
export function unlock(stage: StageId) { update((s) => { if (!s.unlocked.includes(stage)) s.unlocked.push(stage); }); }
export function complete(stage: StageId) { update((s) => { if (!s.completed.includes(stage)) s.completed.push(stage); }); }
export function addUnique(list: 'flavors' | 'cards' | 'collected' | 'achievements' | 'coffees', id: string): boolean {
  const s = save(); if (s[list].includes(id)) return false; s[list].push(id); persist(); return true;
}
export function resetSave() { cache = fresh(); persist(); }
export const level3Revealed = () => save().fakeEndingSeen || save().unlocked.includes('cafe');
