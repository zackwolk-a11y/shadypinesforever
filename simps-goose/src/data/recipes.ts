/**
 * Lab ingredients + recipes. Every ingredient is a Simps Modern Beverage product found on
 * simpsmb.com product listings (soda concentrates + flavoured syrups). Orange is NOT in the
 * Simps catalog, so "Tropical Launch" uses Mango + Coconut. Recipes and powers are fictional.
 */
import { C } from '../art/palette';
import { R, type Ramp } from '../art/palette';
export type IngredientId = 'cola' | 'cream' | 'cherry' | 'rootbeer' | 'lemonlime' | 'vanilla' | 'mango' | 'coconut' | 'blueraspberry' | 'strawberry';
export interface Ingredient { id: IngredientId; name: string; line: 'SODA CONCENTRATE' | 'SYRUP'; ramp: Ramp; color: number }
export const INGREDIENTS: Ingredient[] = [
  { id: 'cola', name: 'COLA', line: 'SODA CONCENTRATE', ramp: R.cola, color: C.cola1 },
  { id: 'cream', name: 'CREAM SODA', line: 'SODA CONCENTRATE', ramp: R.cream, color: C.crm1 },
  { id: 'cherry', name: 'BLACK CHERRY', line: 'SODA CONCENTRATE', ramp: R.cherry, color: C.chr1 },
  { id: 'rootbeer', name: 'ROOT BEER', line: 'SODA CONCENTRATE', ramp: R.rootbeer, color: C.rbr1 },
  { id: 'lemonlime', name: 'LEMON LIME', line: 'SODA CONCENTRATE', ramp: R.lime, color: C.lim1 },
  { id: 'vanilla', name: 'VANILLA', line: 'SYRUP', ramp: [C.wht, C.crm0, C.crm1, C.crm2], color: C.crm0 },
  { id: 'mango', name: 'MANGO', line: 'SYRUP', ramp: R.mango, color: C.mng1 },
  { id: 'coconut', name: 'COCONUT', line: 'SYRUP', ramp: [0xffffff, C.wl0, C.wl2, C.wl3], color: C.wl1 },
  { id: 'blueraspberry', name: 'BLUE RASPBERRY', line: 'SYRUP', ramp: R.blue, color: C.blu1 },
  { id: 'strawberry', name: 'STRAWBERRY', line: 'SYRUP', ramp: [C.pink, C.chr0, C.chr1, C.chr2], color: C.chr0 },
];
export const ING = Object.fromEntries(INGREDIENTS.map((i) => [i.id, i])) as Record<IngredientId, Ingredient>;

export type PowerId = 'cola' | 'cream' | 'cherry' | 'rocket' | 'cloud9' | 'tropical' | 'shield' | 'electric' | 'float' | 'pinkfizz';
export interface PowerDef { id: PowerId; name: string; power: string; hint: string; icon: string; color: number; light: number; duration: number }
export const POWERS: Record<PowerId, PowerDef> = {
  cola: { id: 'cola', name: 'COLA', power: 'FIZZY DASH', hint: 'C: DASH! SMASH BOXES', icon: 'icon_cola', color: C.cola1, light: C.cola0, duration: 45 },
  cream: { id: 'cream', name: 'CREAM SODA', power: 'FOAM FLOAT', hint: 'C: FOAM CLOUD LIFT', icon: 'icon_cream', color: C.crm1, light: C.crm0, duration: 45 },
  cherry: { id: 'cherry', name: 'BLACK CHERRY', power: 'CHERRY BLAST', hint: 'C: BOUNCING CHERRY', icon: 'icon_cherry', color: C.chr1, light: C.chr0, duration: 45 },
  rocket: { id: 'rocket', name: 'CHERRY ROCKET', power: 'CHERRY ROCKET', hint: 'C: ROCKET DASH + FIZZ TRAIL', icon: 'icon_rocket', color: C.chr1, light: C.chr0, duration: 60 },
  cloud9: { id: 'cloud9', name: 'CLOUD NINE', power: 'CLOUD NINE', hint: 'C: BIG LASTING FOAM CLOUD', icon: 'icon_cloud9', color: C.crm1, light: C.crm0, duration: 60 },
  tropical: { id: 'tropical', name: 'TROPICAL LAUNCH', power: 'TROPICAL LAUNCH', hint: 'C: BLAST STRAIGHT UP', icon: 'icon_tropical', color: C.mng1, light: C.mng0, duration: 60 },
  shield: { id: 'shield', name: 'DARK FOAM SHIELD', power: 'FOAM SHIELD', hint: 'C: PROTECTIVE BUBBLE', icon: 'icon_shield', color: C.chr2, light: C.chr0, duration: 60 },
  electric: { id: 'electric', name: 'ELECTRIC FIZZ', power: 'ELECTRIC FIZZ', hint: 'C: RICOCHET ZAP BUBBLE', icon: 'icon_electric', color: C.blu1, light: C.blu0, duration: 60 },
  float: { id: 'float', name: 'ROOT BEER FLOAT', power: 'FLOAT', hint: 'HOLD JUMP TO HOVER', icon: 'icon_float', color: C.rbr1, light: C.rbr0, duration: 60 },
  pinkfizz: { id: 'pinkfizz', name: 'PINK FIZZ', power: 'TRIPLE CHERRY', hint: 'C: TRIPLE SPREAD SHOT', icon: 'icon_pinkfizz', color: C.chr0, light: C.pink, duration: 60 },
};
export interface Recipe { id: string; a: IngredientId; b: IngredientId; power: PowerId; secret?: boolean; drink: number }
export const RECIPES: Recipe[] = [
  { id: 'cherry_rocket', a: 'cola', b: 'cherry', power: 'rocket', drink: C.chr2 },
  { id: 'cloud_nine', a: 'cream', b: 'vanilla', power: 'cloud9', drink: C.crm0 },
  { id: 'tropical_launch', a: 'mango', b: 'coconut', power: 'tropical', drink: C.mng0 },
  { id: 'dark_foam_shield', a: 'cherry', b: 'cream', power: 'shield', drink: C.chr3 },
  { id: 'electric_fizz', a: 'blueraspberry', b: 'lemonlime', power: 'electric', drink: C.blu0 },
  { id: 'root_beer_float', a: 'rootbeer', b: 'vanilla', power: 'float', drink: C.rbr0, secret: true },
  { id: 'pink_fizz', a: 'strawberry', b: 'lemonlime', power: 'pinkfizz', drink: C.pink, secret: true },
];
export const RECIPE_NAME: Record<string, string> = { cherry_rocket: 'CHERRY ROCKET', cloud_nine: 'CLOUD NINE', tropical_launch: 'TROPICAL LAUNCH', dark_foam_shield: 'DARK FOAM SHIELD', electric_fizz: 'ELECTRIC FIZZ', root_beer_float: 'ROOT BEER FLOAT', pink_fizz: 'PINK FIZZ' };
/** Find a recipe among the chosen ingredients (any pair matches, base first). */
export function matchRecipe(base: IngredientId, primary: IngredientId, secondary: IngredientId | null): Recipe | null {
  const pairs: [IngredientId, IngredientId][] = [[base, primary]];
  if (secondary) pairs.push([base, secondary], [primary, secondary]);
  for (const [x, y] of pairs) for (const r of RECIPES) if ((r.a === x && r.b === y) || (r.a === y && r.b === x)) return r;
  return null;
}
/** Unknown combos still give something fun: a basic power picked from the ingredients. */
export function mysteryPower(base: IngredientId): PowerId {
  return base === 'cola' ? 'cola' : base === 'cream' || base === 'vanilla' || base === 'coconut' ? 'cream' : 'cherry';
}
