/** Achievement table + unlock helper (persists, emits a HUD toast). */
import { addUnique, save } from '../systems/save';
export const ACHIEVEMENTS: { id: string; name: string; desc: string }[] = [
  { id: 'first_honk', name: 'FIRST HONK', desc: 'HONK FOR THE FIRST TIME.' },
  { id: 'flavor_explorer', name: 'FLAVOR EXPLORER', desc: 'SAMPLE COLA, CREAM SODA AND BLACK CHERRY.' },
  { id: 'bubble_trouble', name: 'BUBBLE TROUBLE', desc: 'FINISH LEVEL 1.' },
  { id: 'perfect_mix', name: 'PERFECT MIX', desc: 'MIX A PERFECT DRINK IN THE LAB.' },
  { id: 'mixologist', name: 'MIXOLOGIST', desc: 'DISCOVER 5 RECIPES.' },
  { id: 'secret_recipe', name: 'SECRET RECIPE', desc: 'DISCOVER A SECRET RECIPE.' },
  { id: 'goose_stepper', name: 'GOOSE STEPPER', desc: 'BOP 10 SODA CREATURES.' },
  { id: 'master_of_fizz', name: 'MASTER OF FIZZ', desc: 'DEFEAT THE CARBONATION CATASTROPHE.' },
  { id: 'coffee_break', name: 'COFFEE BREAK', desc: 'MAKE A SPECIALTY COFFEE.' },
  { id: 'super_burp', name: 'SUPER BURP', desc: 'UNLEASH THE SUPER BURP.' },
  { id: 'friend_of_ogopogo', name: 'FRIEND OF OGOPOGO', desc: 'SHARE THE LAST SIP.' },
  { id: 'proudly_canadian', name: 'PROUDLY CANADIAN', desc: 'FIND 6 GOLDEN MAPLE LEAVES.' },
  { id: 'certified', name: 'SIMPS CERTIFIED', desc: 'COLLECT 3 CERTIFIED BADGES.' },
  { id: 'honk_if_you_work_here', name: 'HONK IF YOU WORK HERE', desc: 'FINISH THE GREAT SIMPS STOCK-UP.' },
  { id: 'master_stocker', name: 'MASTER STOCKER', desc: 'PUT AWAY EVERY BOX WITHOUT DROPPING ONE.' },
  { id: 'special_delivery', name: 'SPECIAL DELIVERY, EH!', desc: 'LOAD THE TRUCK BEFORE THE BONUS TIMER EXPIRES.' },
  { id: 'double_bubble', name: 'DOUBLE BUBBLE', desc: "FINISH DAVE'S BUBBLE WORKSHOP." },
  { id: 'rainbow_soda', name: 'RAINBOW SODA', desc: "BREW GERRY'S EXPERIMENTAL SODA." },
  { id: 'golden_goose', name: 'GOLDEN GOOSE', desc: 'FINISH THE GAME AND EARN THE GOLDEN GOOSE TOKEN.' },
];
let emitter: { emit: (n: string, ...a: unknown[]) => void } | null = null;
export const bindAchievements = (e: typeof emitter) => { emitter = e; };
export function achieve(id: string) {
  if (!ACHIEVEMENTS.find((a) => a.id === id)) return;
  if (addUnique('achievements', id)) emitter?.emit('hud:achievement', ACHIEVEMENTS.find((a) => a.id === id)!.name);
}
export const hasAch = (id: string) => save().achievements.includes(id);
