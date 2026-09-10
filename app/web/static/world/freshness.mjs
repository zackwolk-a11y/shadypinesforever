// Data-freshness verdict for the World View status line. This module is
// deliberately walled off from every Village data source: it is handed
// nothing but the outcome of the real Fishbowl read requests and the
// wall-clock time of the last fully successful snapshot, and it returns
// one of three states. It cannot — and must not — invent, substitute, or
// interpolate Village activity; when reads fail all it does is downgrade
// the verdict so the visitor knows the room on screen is no longer live.

// A poll cycle is 2s. FRESH_AFTER_MS covers one cycle plus generous slack
// (a slow network, a single dropped request); past it the world on screen
// is no longer guaranteed current. Past STALE_AFTER_MS the last snapshot
// is simply too old to present as the Village's state at all.
export const FRESH_AFTER_MS = 12000;
export const STALE_AFTER_MS = 45000;
// Independent of age: this many consecutive failed polls means the
// connection is down regardless of how recent the last good snapshot was.
export const FAILURES_BEFORE_UNAVAILABLE = 5;

export const STATES = ['fresh', 'stale', 'unavailable'];

export const FRESHNESS_COPY = {
  fresh: 'Live · connected to the Village',
  stale: 'Reconnecting · showing the last confirmed snapshot',
  unavailable: 'Disconnected · no confirmed data from the Village',
};

// inputs:
//   now                  Date.now() at the moment of asking
//   lastSnapshotAt       Date.now() when the last FULLY successful
//                        adapter.poll() returned, or null if none ever did
//   lastPollOk           did the most recent poll attempt succeed?
//   consecutiveFailures  failed polls since the last successful one
export function freshness({now, lastSnapshotAt, lastPollOk, consecutiveFailures = 0}) {
  if (lastSnapshotAt == null) {
    return {state: 'unavailable', reason: 'no-snapshot', ageMs: null};
  }
  const ageMs = Math.max(0, now - lastSnapshotAt);
  if (ageMs >= STALE_AFTER_MS || consecutiveFailures >= FAILURES_BEFORE_UNAVAILABLE) {
    return {
      state: 'unavailable',
      reason: consecutiveFailures >= FAILURES_BEFORE_UNAVAILABLE ? 'polls-failing' : 'snapshot-too-old',
      ageMs,
    };
  }
  if (!lastPollOk || ageMs >= FRESH_AFTER_MS) {
    return {state: 'stale', reason: lastPollOk ? 'snapshot-aging' : 'poll-failed', ageMs};
  }
  return {state: 'fresh', reason: 'current', ageMs};
}

// The status-line text: the base copy for the state plus, when we are not
// fresh, roughly how long ago the last real snapshot arrived. It never
// says anything about Village contents — only about the connection.
export function freshnessLine(verdict) {
  const base = FRESHNESS_COPY[verdict.state] ?? FRESHNESS_COPY.unavailable;
  if (verdict.state === 'fresh' || verdict.ageMs == null) return base;
  const secs = Math.round(verdict.ageMs / 1000);
  const ago = secs < 90 ? `${secs}s` : `${Math.round(secs / 60)}m`;
  return `${base} · last update ${ago} ago`;
}
