import {VillageAdapter,get,API,pretty} from './adapter.mjs';
import {WorldScene,CAST,COLORS} from './scene.mjs';
import {ZONES} from './navigation.mjs';
const $=id=>document.getElementById(id);
const adapter=new VillageAdapter();let snapshot=null,busy=false,polling=false,pendingPoll=false,selected=null,detailGeneration=0,toastTimer;
const scene=new WorldScene($('world'),select);
const element=(tag,text,cls)=>{const el=document.createElement(tag);if(text!=null)el.textContent=text;if(cls)el.className=cls;return el;};
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,7000);}
function setControls(){document.querySelectorAll('[data-control],#message-form button[type=submit]').forEach(b=>b.disabled=busy||!snapshot||scene.stale);$('pause').hidden=Boolean(snapshot?.dashboard.clock.is_paused);$('resume').hidden=!snapshot?.dashboard.clock.is_paused;}
async function poll(){
 if(document.hidden)return;
 if(polling){pendingPoll=true;return;}
 polling=true;
 try{
  const next=await adapter.poll();snapshot=next;scene.apply(next);document.body.dataset.stale='false';
  const {clock,providers}=next.dashboard;$('clock').textContent=`DAY ${clock.day} · ${clock.period}${clock.is_paused?' · PAUSED':''}`;
  const live=providers.llm_is_live||providers.research_is_live;
  $('connection').textContent=`${live?'Connected to Village':'Fixture preview · test data'} · updated ${new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}`;
  $('load-state').hidden=true;renderRoster();
  if(next.events[0])$('last-event').textContent=next.events[0].headline;
  if(next.newEvents.some(e=>/BELIEF_REVISED|BELIEF_UPDATED/.test(e.event_type)))toast('A resident revised a belief. Open their details to read the change.');
  if(next.newEvents.some(e=>e.event_type==='FOUNDER_MESSAGE_DELIVERED'))sound.cue();
 }catch(e){scene.stale=true;document.body.dataset.stale='true';$('connection').textContent='Connection interrupted · retrying';if(!snapshot){$('load-state').textContent=e.message;$('load-state').hidden=false;}}
 finally{polling=false;setControls();if(pendingPoll){pendingPoll=false;queueMicrotask(poll);}}
}
let rosterSignature='';
function renderRoster(){
 const signature=JSON.stringify(snapshot.agents.map(a=>[a.agent_id,a.name,a.current_location,a.visual_location,a.current_activity]));if(signature===rosterSignature)return;rosterSignature=signature;
 $('roster').replaceChildren();const recipientValue=$('recipient').value;$('recipient').replaceChildren(new Option('All residents',''));
 $('resident-count').textContent=String(snapshot.agents.length).padStart(2,'0');
 for(const a of snapshot.agents){const i=CAST.indexOf(a.agent_id.replace('agent_',''));const b=element('button');b.style.setProperty('--resident-color',COLORS[i]??'#bcc7a2');
  const dot=element('span',null,'portrait-dot'),wrap=element('span');wrap.append(element('span',a.name,'resident-name'),element('span',ZONES[a.visual_location]?.label??'Location unavailable','resident-location'),element('span',pretty(a.current_activity)||'quiet','resident-activity'));
  b.append(dot,wrap);b.title=`${a.name} · ${pretty(a.current_activity)||'quiet'} · ${a.current_location??'location unavailable'}`;b.onclick=()=>select({kind:'agent',id:a.agent_id});$('roster').append(b);$('recipient').append(new Option(a.name,a.agent_id));
 }$('recipient').value=recipientValue;
}
function link(parent,text,path){const a=element('a',text,'detail-link');a.href='/fishbowl/'+path;parent.append(a);}
function entry(parent,title,text,meta){const block=element('div',null,'entry');if(title)block.append(element('span',title,'tag'));if(text)block.append(element('p',text));if(meta)block.append(element('small',meta));parent.append(block);return block;}
function group(parent,title,items,render){if(!items?.length)return;parent.append(element('h3',title));for(const item of items.slice(0,12))render(item);}
function action(parent,text,fn){const b=element('button',text);b.onclick=fn;parent.append(b);return b;}
async function select(hit){
 const generation=++detailGeneration;selected=hit;$('detail-content').replaceChildren(element('p','Opening the record…','muted'));$('follow').hidden=hit.kind!=='agent';
 if(!$('details').open)$('details').show();
 if(hit.kind==='agent'){scene.center(hit.id);$('follow').textContent=scene.follow===hit.id?'Stop following':'Follow resident';}
 try{
  const fragment=document.createDocumentFragment();
  if(hit.kind==='agent'){
   const a=await get(`/agents/${encodeURIComponent(hit.id)}`);fragment.append(element('div','RESIDENT','eyebrow'),element('h2',a.name),element('p',`${ZONES[a.current_location]?.label??a.current_location??'Location unavailable'} · ${pretty(a.current_activity)||'quiet'}`,'muted'));
   fragment.append(element('p',a.identity));
   const visual=snapshot?.agents.find(x=>x.agent_id===hit.id);
   if(visual?.visual_location&&visual.visual_location!==a.current_location)fragment.append(element('p','Gathered at '+(ZONES[visual.visual_location]?.label??visual.visual_location)+' for the current conversation.','muted'));
   if(a.conversation_id!=null)action(fragment,'Read current conversation',()=>select({kind:'conversation',id:a.conversation_id}));
   if(a.current_research_id)action(fragment,'Read current research',()=>select({kind:'research',id:a.current_research_id}));
   group(fragment,'Open questions',a.questions.filter(q=>['OPEN','RESEARCHING'].includes(q.status)),q=>entry(fragment,q.status,q.question));
   group(fragment,'Recent memories',a.memories,m=>entry(fragment,m.memory_type,m.content,`Day ${m.created_sim_day??'—'}`));
   group(fragment,'Research threads',a.research_sessions,r=>{const e=entry(fragment,r.status,r.question);action(e,'Read research',()=>select({kind:'research',id:r.research_id}));});
   group(fragment,'Beliefs',a.beliefs,b=>entry(fragment,b.status,b.statement,`${b.confidence}% confidence`));
   group(fragment,'Relationships',a.relationships,r=>entry(fragment,r.other_agent_name,r.notes,`${r.interaction_count} interactions · trust ${r.trust_score} · familiarity ${r.familiarity}`));
   const recent=await get(`/events?agent=${encodeURIComponent(hit.id)}&limit=8`);group(fragment,'Recent actions',recent.events,e=>entry(fragment,pretty(e.event_type),e.headline));
   link(fragment,'Inspect in Fishbowl ↗','agents/'+encodeURIComponent(hit.id));
  }else if(hit.kind==='conversation'){
   const c=await get(`/conversations/${hit.id}`);fragment.append(element('div',c.status,'eyebrow'),element('h2',c.current_subject||'A conversation'),element('p',c.participants.map(a=>a.name).join(' · '),'muted'));
   if(!c.messages.length)fragment.append(element('p','No words have been recorded yet.','muted'));
   for(const m of c.messages)entry(fragment,m.agent_name,m.content,`Turn ${m.turn_number}`);
   link(fragment,'Full conversation in Fishbowl ↗','conversations/'+hit.id);
  }else if(hit.kind==='conversations'){
   fragment.append(element('div','IN CONVERSATION','eyebrow'),element('h2','Around the room'));
   for(const c of snapshot.allConversations.slice(0,15)){const e=entry(fragment,c.status,c.current_subject||c.participants.map(a=>a.name).join(' & '));action(e,'Read conversation',()=>select({kind:'conversation',id:c.id}));}
   link(fragment,'All conversations ↗','conversations');
  }else if(hit.kind==='research'){
   const r=await get(`/research/${encodeURIComponent(hit.id)}`);fragment.append(element('div',r.status,'eyebrow'),element('h2',r.question));
   entry(fragment,r.evidence_strength,r.interpretation);
   group(fragment,'Findings',r.findings,f=>entry(fragment,f.classification,f.finding_text));
   group(fragment,'Sources',r.sources,s=>entry(fragment,s.domain,s.title));
   link(fragment,'Research, claims and sources in Fishbowl ↗','research/'+encodeURIComponent(hit.id));
  }else if(hit.kind==='wall'||hit.kind==='post'){
   fragment.append(element('div','SHARED DISCOVERIES','eyebrow'),element('h2','Research Wall'));
   const posts=hit.post?[hit.post]:snapshot.wall;
   if(!posts.length)fragment.append(element('p','Nothing has been pinned here yet.','muted'));
   for(const p of posts){const e=entry(fragment,p.post_type,p.content,p.agent_name);if(p.related_research_id)action(e,'Read linked research',()=>select({kind:'research',id:p.related_research_id}));if(p.related_rabbit_hole_id)action(e,'Follow rabbit hole',()=>select({kind:'hole',id:p.related_rabbit_hole_id}));}
   link(fragment,'Inspect Research Wall ↗','wall');
  }else if(hit.kind==='holes'){
   fragment.append(element('div','UNFINISHED QUESTIONS','eyebrow'),element('h2','Rabbit Holes'));
   if(!snapshot.holes.length)fragment.append(element('p','No shared investigation has formed yet.','muted'));
   for(const h of snapshot.holes){const e=entry(fragment,h.status,h.title);action(e,'Explore thread',()=>select({kind:'hole',id:h.id}));}
   link(fragment,'All rabbit holes ↗','rabbit-holes');
  }else if(hit.kind==='hole'){
   const h=await get(`/rabbit-holes/${hit.id}`);fragment.append(element('div',h.status,'eyebrow'),element('h2',h.title));entry(fragment,h.evidence_strength,h.description);entry(fragment,'Current hypothesis',h.current_hypothesis);
   group(fragment,'Open questions',h.open_questions,q=>entry(fragment,null,q));group(fragment,'Counterarguments',h.counterarguments,q=>entry(fragment,null,q));link(fragment,'Inspect thread in Fishbowl ↗','rabbit-holes/'+hit.id);
  }else if(hit.kind==='event'){
   const e=hit.event;fragment.append(element('div',pretty(e.event_type),'eyebrow'),element('h2',e.agent_name||'The Village'));entry(fragment,null,e.payload?.public_dialogue||e.payload?.finding_text||e.headline);link(fragment,'Open Fishbowl ↗','');
  }
  if(generation===detailGeneration)$('detail-content').replaceChildren(fragment);
 }catch(e){if(generation===detailGeneration)$('detail-content').replaceChildren(element('p',e.message),element('p','The last world snapshot remains visible.','muted'));}
}
async function control(name,confirmed=false,body){
 if(busy)return;
 if(name==='run-day'&&!confirmed&&(snapshot?.dashboard.providers.llm_is_live||snapshot?.dashboard.providers.research_is_live)){$('day-dialog').showModal();return;}
 busy=true;setControls();toast(name==='founder-message'?'Sending your message…':'The Village is working…');
 try{
  // Mutations are never automatically retried. A timed-out client could duplicate an action.
  const response=await fetch(`${API}/control/${name}${confirmed?'?confirmed=true':''}`,{method:'POST',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});
  const raw=await response.text();let result;try{result=JSON.parse(raw);}catch{throw new Error(`The engine returned an error (${response.status}).`);}
  if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:`Control failed (${response.status})`);
  toast(result.message);
  if(name==='founder-message'&&result.ok){$('message-dialog').close();$('message').value='';sound.cue();}
  // Run Day/Run Period/Next Event have already fully executed on the
  // backend by the time this resolves — this poll() only fetches what
  // happened. adapter.poll()'s before_id backfill loop keeps paging until
  // it reaches the previous cursor, so the ENTIRE backlog (not just the
  // newest 200 rows) arrives here in one shot and gets queued for replay
  // by scene.apply() at whatever speed the visitor has chosen.
  await poll();
 }catch(e){toast(e.message+' Check Fishbowl before trying again.');}
 finally{busy=false;setControls();}
}
// Optional, quiet synthesized room tone; no external audio or autoplay.
const sound={ctx:null,muted:true,async toggle(){
 if(!this.ctx){this.ctx=new AudioContext();this.gain=this.ctx.createGain();this.gain.gain.value=.008;this.gain.connect(this.ctx.destination);for(const f of [65,98]){const o=this.ctx.createOscillator();o.frequency.value=f;o.connect(this.gain);o.start();}}
 this.muted=!this.muted;if(this.muted)await this.ctx.suspend();else await this.ctx.resume();$('sound').textContent=this.muted?'Sound off':'Sound on';$('sound').setAttribute('aria-pressed',String(!this.muted));
 },cue(){if(!this.ctx||this.muted)return;const o=this.ctx.createOscillator(),g=this.ctx.createGain();o.frequency.value=440;g.gain.setValueAtTime(.02,this.ctx.currentTime);g.gain.exponentialRampToValueAtTime(.001,this.ctx.currentTime+.6);o.connect(g);g.connect(this.ctx.destination);o.start();o.stop(this.ctx.currentTime+.6);}};
$('sound').onclick=()=>sound.toggle().catch(()=>toast('Sound could not start in this browser.'));
$('zoom-in').onclick=()=>scene.zoom(1.15);$('zoom-out').onclick=()=>scene.zoom(.85);$('reset').onclick=()=>scene.reset();
// Replay controls affect ONLY how fast this tab plays back already-persisted
// events (scene.speed / scene.skipToLive) — never the backend, which has
// already finished running by the time any of this is visible.
for(const b of document.querySelectorAll('.speed-btn'))b.onclick=()=>{
 scene.setSpeed(Number(b.dataset.speed));
 for(const x of document.querySelectorAll('.speed-btn'))x.setAttribute('aria-pressed',String(x===b));
};
$('skip-live').onclick=()=>scene.skipToLive();
// A light, independent ticker (not tied to the 2s network poll) so
// "Replaying N of M" advances smoothly as the queue drains between polls.
setInterval(()=>{
 const rs=scene.replayStatus();
 $('replay-bar').hidden=!rs.active;
 if(rs.active)$('replay-status').textContent=`Replaying ${rs.done} of ${rs.total}`;
},200);
// Read-only introspection for tests/tools — never written to by the page.
window.__world={scene,adapter};
$('close-detail').onclick=()=>{$('details').close();detailGeneration++;};
$('follow').onclick=()=>{if(selected?.kind==='agent'){scene.follow=scene.follow===selected.id?null:selected.id;$('follow').textContent=scene.follow?'Stop following':'Follow resident';}};
$('message-open').onclick=()=>$('message-dialog').showModal();$('cancel-message').onclick=()=>$('message-dialog').close();
$('message-form').onsubmit=e=>{e.preventDefault();control('founder-message',false,{content:$('message').value,target_agent_id:$('recipient').value||null});};
$('cancel-day').onclick=()=>$('day-dialog').close();$('confirm-day').onclick=()=>{$('day-dialog').close();control('run-day',true);};
for(const b of document.querySelectorAll('[data-control]'))b.onclick=()=>control(b.dataset.control);
window.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('details').open){$('details').close();detailGeneration++;}});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
setControls();
try{await scene.start();await poll();setInterval(poll,2000);}catch(e){$('load-state').textContent=e.message;}
