/** Per-run session state (score, hearts, time, coffee). Survives scene changes and the fake ending. */
import { save, update } from './save';
export type RunMode = 'story' | 'demo' | 'stage';
class GameStateImpl {
  score = 0; hearts = 5; maxHearts = 5; time = 0; mode: RunMode = 'story';
  coffee: string | null = null; deaths = 0;
  events: { emit: (n: string, ...a: unknown[]) => void } | null = null;
  newRun(mode: RunMode) { this.score = 0; this.hearts = this.maxHearts; this.time = 0; this.mode = mode; this.deaths = 0; if (mode !== 'stage') this.coffee = null; else this.coffee = save().coffee; this.persistRun(); }
  resume() { const r = save().run; if (r) { this.score = r.score; this.hearts = Math.max(1, r.hearts); this.time = r.time; this.coffee = r.coffee; this.mode = 'story'; } }
  addScore(n: number) { this.score += n; this.events?.emit('hud:score', this.score); }
  persistRun() { if (this.mode === 'demo') return; update((s) => { s.run = { score: this.score, hearts: this.hearts, time: this.time, coffee: this.coffee }; s.coffee = this.coffee ?? s.coffee; }); }
  finishRun() { update((s) => { s.lastScore = this.score; s.bestScore = Math.max(s.bestScore, this.score); s.bestTime = s.bestTime ? Math.min(s.bestTime, this.time) : this.time; }); }
}
export const GS = new GameStateImpl();
