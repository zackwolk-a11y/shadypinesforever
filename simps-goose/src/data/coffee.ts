/**
 * Café syrups (Simps Café Series — Vanilla, Salted Caramel, Hazelnut, Peppermint, Lavender,
 * Toasted Marshmallow are all listed on simpsmb.com) → bubble-burp powers (fictional).
 * Balance target: every burp kills Ogopogo in a similar time (damage-per-second ≈ 1.1–1.3).
 */
import { C } from '../art/palette';
export type BurpId = 'vanilla' | 'saltedcaramel' | 'hazelnut' | 'peppermint' | 'lavender' | 'marshmallow';
export interface Burp {
  id: BurpId; syrup: string; power: string; desc: string; color: number; light: number;
  dmg: number; speed: number; size: number; gravity: number; cooldown: number; bounces: number; life: number;
  stun: number; shield?: boolean; multi?: number;
}
export const BURPS: Record<BurpId, Burp> = {
  vanilla: { id: 'vanilla', syrup: 'VANILLA', power: 'GENTLE GIANT', desc: 'HUGE SLOW BUBBLES. EASY TO HIT WITH.', color: C.crm1, light: C.crm0, dmg: 3, speed: 95, size: 30, gravity: -12, cooldown: 0.75, bounces: 0, life: 4.5, stun: 0.6 },
  saltedcaramel: { id: 'saltedcaramel', syrup: 'SALTED CARAMEL', power: 'HEAVY BURP', desc: 'HEAVY ARCING BUBBLES THAT HIT HARD.', color: C.gold2, light: C.gold1, dmg: 4, speed: 210, size: 20, gravity: 330, cooldown: 0.95, bounces: 1, life: 3, stun: 0.9 },
  hazelnut: { id: 'hazelnut', syrup: 'HAZELNUT', power: 'RICOCHET', desc: 'BOUNCES OFF WALLS, WATER AND ROCKS.', color: C.cola0, light: C.wd0, dmg: 2, speed: 230, size: 16, gravity: 0, cooldown: 0.5, bounces: 4, life: 3.5, stun: 0.4 },
  peppermint: { id: 'peppermint', syrup: 'PEPPERMINT', power: 'RAPID FIZZ', desc: 'FAST LITTLE MINTY BURSTS.', color: C.lim1, light: 0xd8fff0, dmg: 1, speed: 300, size: 11, gravity: 0, cooldown: 0.22, bounces: 0, life: 1.6, stun: 0.15 },
  lavender: { id: 'lavender', syrup: 'LAVENDER', power: 'DREAM BUBBLE', desc: 'SLOW BUBBLES THAT FREEZE WAVES AND STUN LONGER.', color: C.pur1, light: C.pur0, dmg: 2, speed: 120, size: 22, gravity: -20, cooldown: 0.55, bounces: 0, life: 4, stun: 1.6 },
  marshmallow: { id: 'marshmallow', syrup: 'TOASTED MARSHMALLOW', power: 'WARM FOAM', desc: 'EVERY BURP ALSO WRAPS YOU IN A FOAM SHIELD.', color: C.crm2, light: C.wht, dmg: 2, speed: 170, size: 18, gravity: 40, cooldown: 0.55, bounces: 0, life: 3, stun: 0.5, shield: true },
};
export const BURP_ORDER: BurpId[] = ['vanilla', 'saltedcaramel', 'hazelnut', 'peppermint', 'lavender', 'marshmallow'];
export const COFFEE_BASES = ['ESPRESSO', 'DOUBLE ESPRESSO', 'COLD BREW'] as const;
export const MILKS = ['WHOLE MILK', 'OAT MILK', 'ALMOND MILK', 'NO MILK'] as const;
export const LATTE_ART = ['MAPLE LEAF', 'TRIDENT', 'HEART', 'GOOSE'] as const;
