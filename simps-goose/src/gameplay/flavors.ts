/**
 * Flavour data. Names are verified Simps Modern Beverage soda concentrates
 * (Cola, Cream Soda, Black Cherry). Powers are fictional gameplay abilities.
 */
import { C } from '../art/palette';
export type FlavorId = 'cola' | 'cream' | 'cherry';
export interface Flavor {
  id: FlavorId; name: string; power: string; hint: string;
  color: number; light: number; icon: string; react: string; staffLine: string; gooseThought: string;
}
export const FLAVORS: Record<FlavorId, Flavor> = {
  cola: { id: 'cola', name: 'COLA', power: 'FIZZY DASH', hint: 'C: DASH! SMASH BOXES', color: C.cola1, light: C.cola0, icon: 'icon_cola', react: 'reactFizz', staffLine: 'OUR CLASSIC COLA!', gooseThought: 'FIZZ!!' },
  cream: { id: 'cream', name: 'CREAM SODA', power: 'FOAM FLOAT', hint: 'C: FOAM CLOUD LIFT', color: C.crm1, light: C.crm0, icon: 'icon_cream', react: 'reactDreamy', staffLine: 'SMOOTH, RIGHT?', gooseThought: '*' },
  cherry: { id: 'cherry', name: 'BLACK CHERRY', power: 'CHERRY BLAST', hint: 'C: BOUNCING CHERRY', color: C.chr1, light: C.chr0, icon: 'icon_cherry', react: 'reactSour', staffLine: 'BOLD CHOICE, GOOSE!', gooseThought: '!!' },
};
export const FLAVOR_ORDER: FlavorId[] = ['cola', 'cream', 'cherry'];
export const POWER_DURATION = 45;
