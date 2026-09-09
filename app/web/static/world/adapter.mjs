// Backend data is authoritative. This module has no simulation writer.
export const API = '/fishbowl/api';
export const pretty = value => String(value ?? '').replaceAll('_', ' ').toLowerCase();
export async function get(path) {
  const response = await fetch(API + path, {signal: AbortSignal.timeout(12000), cache:'no-store'});
  if (!response.ok) throw new Error(`Village request failed (${response.status})`);
  return response.json();
}
export const MOTIONS = {
  DO_NOTHING:'idle', REST:'rest', OBSERVE:'observe', LISTEN_TO_MUSIC:'listen',
  DRINK_COFFEE:'coffee', WRITE_NOTE:'write', ASK_QUESTION:'talk', SPEAK:'talk',
  SEND_MESSAGE:'message', START_CONVERSATION:'listen', JOIN_CONVERSATION:'listen',
  LEAVE_CONVERSATION:'idle', START_RESEARCH:'work', POST_TO_WALL:'post',
  READ_WALL_POST:'think', FORM_BELIEF:'think', REVISE_BELIEF:'think', CHALLENGE_CLAIM:'think',
};
export function motionFor(card, event) {
  if (card.current_research_id) return 'work';
  // An event applies only while it is the backend's latest action, never forever.
  if (event && (!card.last_action_at || event.created_at === card.last_action_at)) {
    const actions = event.payload?.actions ?? [];
    const mapped = actions.map(a => MOTIONS[a]).find(Boolean);
    if (mapped) return mapped;
  }
  if (card.conversation_id != null) return 'listen';
  const activity = pretty(card.current_activity);
  if (/research|read|search|synthesi/.test(activity)) return 'work';
  if (/writ|note|zine/.test(activity)) return 'write';
  if (/coffee|espresso/.test(activity)) return 'coffee';
  if (/reflect|think/.test(activity)) return 'think';
  if (/music|listen/.test(activity)) return 'listen';
  if (/rest|sit/.test(activity)) return 'rest';
  return 'idle';
}
export class VillageAdapter {
  // The single source of truth for "what has already been shown" — every
  // event with id <= cursor is considered delivered forever. A control
  // action (Run Day/Run Period/Next Event) never resets this: the very next
  // poll's before_id backfill loop below walks backward from the newest
  // event until it reaches this exact value, so the whole backlog produced
  // by one Run Day surfaces in newEvents, not just the last 200 rows.
  cursor = null;
  // Belt-and-suspenders duplicate guard on top of the `id > cursor` filter
  // below, so a event can never be handed to the visual queue twice even
  // under a pathological retry/backfill overlap. Trimmed like seenMessages.
  emittedEventIds = new Set();
  latestActions = new Map();
  detailCache = new Map();
  get lastSeenEventId() { return this.cursor; }
  async poll() {
    const [dashboard, feed, conversations, research, wall, holes] = await Promise.all([
      get('/dashboard'),get('/events?limit=200'),get('/conversations'),get('/research'),get('/wall'),get('/rabbit-holes'),
    ]);
    if (!dashboard) throw new Error('No simulation clock is available. Open Fishbowl to check the database.');
    let events = feed.events;
    let pages = 0;
    // before_id is the verified backend cursor. No made-up after_id contract.
    // This is what already fetches a Run Day's FULL backlog in one poll: it
    // keeps paging backward until it reaches the previous cursor (or runs
    // out of pages), not just the newest 200 rows.
    while (this.cursor != null && feed.events.length === 200 && events.length && events.at(-1).id > this.cursor && pages++ < 9) {
      const page = await get(`/events?limit=200&before_id=${events.at(-1).id}`);
      if (!page.events.length) break;
      events = events.concat(page.events);
      if (page.events.length < 200) break;
    }
    const first = this.cursor == null;
    // The full ordered stream since last shown — every event, not just the
    // latest one per agent. This is what the visual queue (scene.mjs)
    // replays; `latestActions` below is a separate, narrower thing (an
    // idle-pose fallback for whichever agent isn't currently mid-replay).
    const newEvents = first
      ? []
      : events.filter(e => e.id > this.cursor && !this.emittedEventIds.has(e.id)).reverse();
    for (const e of newEvents) this.emittedEventIds.add(e.id);
    if (this.emittedEventIds.size > 4000) this.emittedEventIds = new Set([...this.emittedEventIds].slice(-2000));
    for (const event of [...events].reverse()) if (event.event_type === 'AGENT_ACTED') this.latestActions.set(event.agent_id,event);
    this.cursor = Math.max(this.cursor ?? 0, ...events.map(e => e.id));
    const active = conversations.conversations.filter(c => c.status !== 'ENDED');
    const conversationDetails = await Promise.all(active.map(async c => {
      const cached = this.detailCache.get(c.id);
      if (cached?.message_count === c.message_count) return {...cached,...c};
      const detail = await get(`/conversations/${c.id}`);
      this.detailCache.set(c.id,detail);
      return detail;
    }));
    for (const id of this.detailCache.keys()) if (!active.some(c=>c.id===id)) this.detailCache.delete(id);
    return {dashboard, events, newEvents, first, conversations:conversationDetails,
      allConversations:conversations.conversations, research:research.sessions,
      wall:wall.posts, holes:holes.rabbit_holes,
      agents:dashboard.agents.map(card=>({...card,visual_location:visualLocation(card,active,dashboard.agents),motion:motionFor(card,this.latestActions.get(card.agent_id))})),
    };
  }
}

// Morning gatherings have no Conversation.location in this backend revision.
// The requested group arrangement uses the communal table as presentation staging;
// two-person gatherings use the first persisted participant's known station.
export function visualLocation(card,conversations,agents){
  const conversation=conversations.find(c=>c.id===card.conversation_id);
  if(!conversation)return card.current_location;
  if(conversation.location)return conversation.location;
  if(conversation.participants?.length>2)return 'communal_table';
  return agents.find(a=>a.agent_id===conversation.participants?.[0]?.agent_id)?.current_location||card.current_location;
}
