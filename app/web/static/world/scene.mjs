import {W,H,ZONES,allocate,route} from './navigation.mjs';
import {MOTIONS} from './adapter.mjs';
export const CAST=['optimisto','vince','questauthor','alien','sol','roxy','dex','lucid'];
export const COLORS=['#cec298','#b98060','#d3ad56','#91bcb1','#c18785','#e0b450','#8fa9bd','#b4be93'];
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
const short=(s,n=86)=>s.length>n?s.slice(0,n-1).trimEnd()+'…':s;
const loadImage=src=>new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error('The clubhouse artwork could not load.'));image.src=src;});
// Clipped original artwork is reused as an occluder; no duplicate furniture texture.
const OCCLUDERS=[
 {depth:600,points:[[661,363],[947,363],[974,479],[978,531],[997,548],[988,563],[964,559],[947,594],[931,594],[927,502],[905,504],[901,595],[886,598],[880,529],[783,531],[778,598],[763,598],[764,540],[693,537],[684,595],[670,594],[663,491],[646,490],[635,559],[624,559],[636,489],[643,393]]},
 {depth:760,points:[[136,571],[185,540],[200,515],[381,521],[526,544],[549,568],[564,575],[571,610],[553,720],[540,735],[386,713],[347,735],[189,745],[178,733],[194,709],[146,664]]},
];
// --- Visual event replay -----------------------------------------------
// Every dwell below is a PRESENTATION timer only — it paces how long this
// browser tab holds a pose before moving to the next already-persisted
// event. It has no effect on the backend: Run Day/Run Period/Next Event
// already ran to completion (and returned) before any of this runs.
const DWELL_ACT=1100, DWELL_GATHER=1000, DWELL_ICON=900, DWELL_FOUNDER=1200;
const dwellForSpeech=text=>clamp(900+(text?.length??0)*35,1200,6000);
// Types with no independent visual meaning of their own — AGENT_WOKE and
// CONVERSATION_MESSAGE are bookkeeping rows (the actual spoken text lives
// on the sibling AGENT_ACTED.payload.public_dialogue); CONVERSATION_ENDED
// needs no staging since the next AGENT_ACTED for each participant already
// walks them to wherever they go next. They still advance the queue (and
// the "N of M" counter) — just with no walk/hold phase attached.
const PASSTHROUGH_TYPES=new Set(['AGENT_WOKE','CONVERSATION_MESSAGE','CONVERSATION_ENDED']);
export class WorldScene {
 constructor(canvas,onSelect){
  this.canvas=canvas;this.ctx=canvas.getContext('2d',{alpha:false});this.onSelect=onSelect;
  this.residents=new Map();this.slots=new Map();this.bubbles=new Map();this.seenMessages=new Set();this.hit=[];
  this.camera={x:768,y:515,zoom:1};this.target={...this.camera};this.follow=null;this.selected=null;
  this.reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;this.last=0;this.snapshot=null;this.stale=false;
  // Visual event queue: FIFO of already-persisted FeedEvent objects
  // (from adapter.mjs's newEvents), replayed one at a time. `playing` is
  // the item currently being walked-to/held; `speed` (1/2/4) scales how
  // fast held dwells and in-replay walking play out — it never reaches
  // the backend. `replayDone`/`replayTotal` back the "Replaying N of M"
  // indicator world.mjs renders.
  this.queue=[];this.playing=null;this.speed=1;this.replayDone=0;this.replayTotal=0;
  this.canvas.addEventListener('wheel',e=>{e.preventDefault();this.zoom(e.deltaY>0?.9:1.1);},{passive:false});
  this.canvas.addEventListener('pointerdown',e=>{this.canvas.setPointerCapture(e.pointerId);this.drag={x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY};});
  this.canvas.addEventListener('pointermove',e=>{if(!this.drag)return;this.follow=null;this.target.x-=(e.clientX-this.drag.x)/this.scale;this.target.y-=(e.clientY-this.drag.y)/this.scale;this.drag.x=e.clientX;this.drag.y=e.clientY;});
  this.canvas.addEventListener('pointerup',e=>{if(this.drag&&Math.hypot(e.clientX-this.drag.startX,e.clientY-this.drag.startY)<7){const p=this.toWorld(e.clientX,e.clientY);const hit=[...this.hit].reverse().find(h=>p.x>=h.x&&p.x<=h.x+h.w&&p.y>=h.y&&p.y<=h.y+h.h);if(hit)this.onSelect(hit);}this.drag=null;});
  this.canvas.addEventListener('pointercancel',()=>{this.drag=null;});
  this.canvas.addEventListener('keydown',e=>{if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','+','-','0'].includes(e.key)){e.preventDefault();this.follow=null;if(e.key==='0')this.reset();else if(e.key==='+')this.zoom(1.1);else if(e.key==='-')this.zoom(.9);else{this.target.x+=e.key==='ArrowRight'?60:e.key==='ArrowLeft'?-60:0;this.target.y+=e.key==='ArrowDown'?60:e.key==='ArrowUp'?-60:0;}}});
  new ResizeObserver(()=>this.resize()).observe(canvas);this.resize();
 }
 async start(){[this.room,this.atlas]=await Promise.all([loadImage('/fishbowl/static/world/assets/clubhouse.png'),loadImage('/fishbowl/static/world/assets/residents.png')]);this.frames=this.prepareFrames();requestAnimationFrame(t=>this.frame(t));}
 prepareFrames(){
  // Alpha-trim each equal atlas cell in memory for consistent foot anchors.
  const scratch=document.createElement('canvas');scratch.width=this.atlas.width;scratch.height=this.atlas.height;
  const c=scratch.getContext('2d',{willReadFrequently:true});c.drawImage(this.atlas,0,0);
  const cw=this.atlas.width/4,ch=this.atlas.height/2,frames=[];
  for(let i=0;i<8;i++){const sx=(i%4)*cw,sy=Math.floor(i/4)*ch;const data=c.getImageData(sx,sy,cw,ch).data;let left=cw,right=0,top=ch,bottom=0;
   for(let y=0;y<ch;y++)for(let x=0;x<cw;x++)if(data[(y*cw+x)*4+3]>120){left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);}
   frames.push({x:sx+left,y:sy+top,w:right-left+1,h:bottom-top+1});
  }return frames;
 }
 resize(){this.width=innerWidth;this.height=innerHeight;const dpr=Math.min(devicePixelRatio||1,2);this.dpr=dpr;this.canvas.width=Math.round(this.width*dpr);this.canvas.height=Math.round(this.height*dpr);this.baseScale=Math.min((this.width>900?this.width-230:this.width)/W,(this.height-145)/H);}
 zoom(factor){this.target.zoom=clamp(this.target.zoom*factor,.65,2.6);}
 reset(){this.follow=null;this.target={x:768,y:515,zoom:1};}
 center(id){const a=this.residents.get(id);if(a){this.selected=id;this.target.x=a.x;this.target.y=a.y-120;this.target.zoom=1.45;}}
 toWorld(x,y){return{x:(x-this.offsetX)/this.scale,y:(y-this.offsetY)/this.scale};}
 bubble(id,text,kind,detail){if(!text||!this.residents.has(id))return;this.bubbles.set(id,{text,kind,detail,until:performance.now()+14000});}
 apply(snapshot){
  this.snapshot=snapshot;this.stale=false;
  // While a backlog is replaying, positions come ONLY from advanceQueue()
  // below — never snap straight to the live/final AgentCard state. Once
  // the queue and any in-flight item both drain, this resumes on the very
  // next apply() (and advanceQueue's own edge-triggered reconcile() below
  // does it immediately, without waiting for that next poll).
  if(!this.isReplaying())this.slots=allocate(snapshot.agents,this.slots);
  const keep=new Set(snapshot.agents.map(a=>a.agent_id));
  for(const id of this.residents.keys())if(!keep.has(id))this.residents.delete(id);
  for(const card of snapshot.agents){
   let a=this.residents.get(card.agent_id);
   if(!a){
    const slot=this.slots.get(card.agent_id);
    const spot=slot?slot.spot:[768,515];
    a={x:spot[0],y:spot[1],path:[],face:1,phase:CAST.indexOf(card.agent_id.replace('agent_',''))*.86};
    this.residents.set(card.agent_id,a);
   }
   a.card=card;
   if(!this.isReplaying()){
    const slot=this.slots.get(card.agent_id);
    if(slot&&a.destination!==slot.spot){a.path=route([a.x,a.y],slot.spot);a.destination=slot.spot;}
   }
  }
  // Live "current conversation" bubble — unchanged from before. This is
  // the idle-state fallback for whichever conversation is active RIGHT
  // NOW; it runs independently of the replay queue below, which handles
  // dialogue for events as they are replayed in order.
  for(const c of snapshot.conversations){
   const message=c.messages.at(-1);if(!message)continue;
   const key=`${c.id}:${message.id}`;if(this.seenMessages.has(key))continue;this.seenMessages.add(key);
   this.bubble(message.agent_id,message.content,'SPEAK',{kind:'conversation',id:c.id});
  }
  if(this.seenMessages.size>1000)this.seenMessages=new Set([...this.seenMessages].slice(-500));
  this.enqueue(snapshot.newEvents);
 }
 // --- Visual event queue -------------------------------------------------
 isReplaying(){return this.queue.length>0||this.playing!=null;}
 replayStatus(){return {active:this.isReplaying(),done:this.replayDone,total:this.replayTotal};}
 setSpeed(n){this.speed=n;}
 enqueue(events){
  if(!events?.length)return;
  if(!this.isReplaying()){this.replayDone=0;this.replayTotal=0;}
  this.queue.push(...events);this.replayTotal+=events.length;
 }
 // Assigns one zone spot to one agent outside the normal allocate() pass
 // (which only ever looks at the CURRENT AgentCard state) — same ZONES
 // table, same "keep the prior spot if it's still free" rule, so replay
 // and live placement never fight over the same seats.
 claimSpot(zoneKey,agentId){
  const zone=ZONES[zoneKey];if(!zone)return null;
  const occupied=[...this.residents.entries()].filter(([id])=>id!==agentId).map(([,a])=>[a.x,a.y]);
  const free=spot=>occupied.every(o=>Math.hypot(o[0]-spot[0],o[1]-spot[1])>39);
  const prior=this.slots.get(agentId);
  const spot=(prior&&prior.zone===zoneKey&&free(prior.spot))?prior.spot:(zone.spots.find(free)||zone.spots[0]);
  this.slots.set(agentId,{zone:zoneKey,spot});
  return spot;
 }
 walkTo(id,zoneKey){
  const a=this.residents.get(id);if(!a)return false;
  if(!ZONES[zoneKey])return false;
  const spot=this.claimSpot(zoneKey,id);if(!spot)return false;
  a.path=(spot[0]!==a.x||spot[1]!==a.y)?route([a.x,a.y],spot):[];
  a.destination=spot;
  return true;
 }
 // Starts one queued event: real movement (via the existing path/tween
 // system) for anything that implies a location, or an immediate hold for
 // anything that's only ever an icon/pose. Returns null for a pass-through
 // event (nothing to wait on — advanceQueue() counts it as done at once).
 beginItem(event,now){
  const et=event.event_type,p=event.payload??{};
  if(PASSTHROUGH_TYPES.has(et))return null;
  if(et==='AGENT_ACTED'){
   const id=event.agent_id;if(!this.residents.has(id))return null;
   this.walkTo(id,p.location);
   const dwell=p.public_dialogue?dwellForSpeech(p.public_dialogue):DWELL_ACT;
   return {event,actors:[id],phase:'walking',dwell,holdStart:null,kind:'act'};
  }
  if(et==='CONVERSATION_STARTED'){
   const ids=(p.participants??[]).filter(id=>this.residents.has(id));
   if(!ids.length)return null;
   const zoneKey=ids.length>2?'communal_table':(this.residents.get(ids[0])?.card?.current_location);
   let moved=false;for(const id of ids)moved=this.walkTo(id,zoneKey)||moved;
   if(!moved)return null;
   return {event,actors:ids,phase:'walking',dwell:DWELL_GATHER,holdStart:null,kind:'gather'};
  }
  if(/REFLECTION|MEMORY/.test(et)){
   const a=this.residents.get(event.agent_id);if(!a)return null;
   a.thoughtUntil=now+5000;
   return {event,actors:[event.agent_id],phase:'holding',dwell:DWELL_ICON,holdStart:now,kind:'icon'};
  }
  if(/RESEARCH_COMPLETED|FINDING_CREATED/.test(et)){
   const a=this.residents.get(event.agent_id);if(!a)return null;
   a.findingUntil=now+8000;
   return {event,actors:[event.agent_id],phase:'holding',dwell:DWELL_ICON,holdStart:now,kind:'icon'};
  }
  if(et==='FOUNDER_MESSAGE_DELIVERED'){
   const ids=(p.recipients??[event.agent_id]).filter(id=>this.residents.has(id));
   if(!ids.length)return null;
   for(const id of ids)this.residents.get(id).founderUntil=now+7000;
   this.founderCueUntil=now+3000;
   return {event,actors:ids,phase:'holding',dwell:DWELL_FOUNDER,holdStart:now,kind:'icon'};
  }
  return null; // any other event type: no distinct visual, just advance
 }
 // Fires the moment every actor in the current item has physically
 // arrived — never before. This is what a bubble/finding icon waits on.
 onArrived(p,now){
  const ep=p.event.payload??{};
  if(p.kind==='act'){
   if(ep.public_dialogue){
    const kind=(ep.actions??[]).includes('ASK_QUESTION')?'ASK_QUESTION':'SPEAK';
    this.bubble(p.event.agent_id,ep.public_dialogue,kind,{kind:'event',event:p.event});
   }else{
    const a=this.residents.get(p.event.agent_id);
    if(a)a.replayMotion=(ep.actions??[]).map(x=>MOTIONS[x]).find(Boolean)??'idle';
   }
  }
  // 'gather': arriving together is the whole visual — no invented dialogue.
  p.holdStart=now;
 }
 // Re-derives every resident's target spot from the latest known live
 // snapshot the instant the queue (and any in-flight item) fully drains —
 // the "final reconciliation" step, tweened (not snapped) like every other
 // move, so it can never look like a teleport even at the seam.
 reconcile(){
  if(!this.snapshot)return;
  this.slots=allocate(this.snapshot.agents,this.slots);
  for(const card of this.snapshot.agents){
   const slot=this.slots.get(card.agent_id);const a=this.residents.get(card.agent_id);
   if(a)a.replayMotion=null;
   if(a&&slot&&a.destination!==slot.spot){a.path=route([a.x,a.y],slot.spot);a.destination=slot.spot;}
  }
 }
 advanceQueue(now){
  const wasReplaying=this.isReplaying();
  if(!this.playing){
   if(!this.queue.length)return;
   const event=this.queue.shift();
   const started=this.beginItem(event,now);
   if(!started){this.replayDone++;}
   else{this.playing=started;if(started.phase==='holding')this.onArrived(started,now);}
  }
  const p=this.playing;
  if(p){
   if(p.phase==='walking'){
    const arrived=p.actors.every(id=>{const a=this.residents.get(id);return !a||a.path.length===0;});
    if(arrived){p.phase='holding';this.onArrived(p,now);}
   }else if(p.phase==='holding'){
    const elapsed=(now-p.holdStart)*this.speed;
    if(elapsed>=p.dwell){this.playing=null;this.replayDone++;}
   }
  }
  if(wasReplaying&&!this.isReplaying())this.reconcile();
 }
 skipToLive(){
  this.queue=[];this.playing=null;this.replayDone=0;this.replayTotal=0;
  this.speed=1;
  if(!this.snapshot)return;
  this.slots=allocate(this.snapshot.agents,this.slots);
  for(const card of this.snapshot.agents){
   const slot=this.slots.get(card.agent_id);const a=this.residents.get(card.agent_id);
   if(a){a.replayMotion=null;}
   if(a&&slot){a.x=slot.spot[0];a.y=slot.spot[1];a.path=[];a.destination=slot.spot;}
  }
 }
 // -------------------------------------------------------------------------
 frame(now){
  const dt=Math.min((now-this.last)/1000||0,.05);this.last=now;
  if(!document.hidden){this.update(dt,now);this.draw(now/1000);}
  requestAnimationFrame(t=>this.frame(t));
 }
 update(dt,now){
  this.advanceQueue(now);
  const replaying=this.isReplaying();
  for(const [id,a] of this.residents){a.walking=false;
   if(a.path.length&&!this.stale){const p=a.path[0],dx=p[0]-a.x,dy=p[1]-a.y,dist=Math.hypot(dx,dy);const step=(this.reduce?500:95)*dt*(replaying?this.speed:1);
    if(dist<=step){a.x=p[0];a.y=p[1];a.path.shift();}else{a.x+=dx/dist*step;a.y+=dy/dist*step;a.walking=true;if(Math.abs(dx)>2)a.face=dx>0?1:-1;}
   }else if(a.card.conversation_partners?.length||a.card.interaction_target){const targets=a.card.interaction_target?[{agent_id:a.card.interaction_target}]:(a.card.conversation_partners??[]);const others=targets.map(p=>this.residents.get(p.agent_id)).filter(Boolean);const closest=others.sort((b,c)=>Math.hypot(a.x-b.x,a.y-b.y)-Math.hypot(a.x-c.x,a.y-c.y))[0];if(closest&&Math.abs(closest.x-a.x)>10)a.face=closest.x>a.x?1:-1;}
   if(this.bubbles.get(id)?.until<now)this.bubbles.delete(id);
  }
  if(this.follow){const a=this.residents.get(this.follow);if(a){this.target.x=a.x;this.target.y=a.y-120;}}
  this.target.x=clamp(this.target.x,100,1436);this.target.y=clamp(this.target.y,150,924);
  for(const k of ['x','y','zoom'])this.camera[k]+=(this.target[k]-this.camera[k])*(this.reduce?1:1-Math.exp(-6*dt));
 }
 draw(t){
  const c=this.ctx,d=this.dpr;c.setTransform(d,0,0,d,0,0);c.fillStyle='#101d1b';c.fillRect(0,0,this.width,this.height);
  this.scale=this.baseScale*this.camera.zoom;const bias=this.width>900?90:0;
  this.offsetX=this.width/2+bias-this.camera.x*this.scale;this.offsetY=this.height/2+12-this.camera.y*this.scale;
  c.translate(this.offsetX,this.offsetY);c.scale(this.scale,this.scale);this.hit=[];
  c.drawImage(this.room,0,0,W,H);
  const period=this.snapshot?.dashboard.clock.period??'NIGHT';
  // Color grade only. Weather is never inferred.
  c.fillStyle={MORNING:'#edca7909',RESEARCH:'#243d420d',AFTERNOON:'#e2d5960b',EVENING:'#4b251923',NIGHT:'#04132642'}[period]??'#04132622';c.fillRect(0,0,W,H);
  if(this.founderCueUntil>performance.now()){c.fillStyle=`rgba(160,211,188,${.06*(this.founderCueUntil-performance.now())/3000})`;c.fillRect(0,0,W,H);}
  this.drawWall(c);
  const layers=[...this.residents.entries()].map(([id,a])=>({depth:a.y,draw:()=>this.drawResident(c,id,a,t)}));
  for(const o of OCCLUDERS)layers.push({depth:o.depth,draw:()=>{c.save();c.beginPath();o.points.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.closePath();c.clip();c.drawImage(this.room,0,0,W,H);c.restore();}});
  layers.sort((a,b)=>a.depth-b.depth).forEach(l=>l.draw());
  this.drawAmbience(c,this.reduce?0:t);
  for(const [id,a]of this.residents)this.drawLabel(c,id,a);
  for(const [id,b]of [...this.bubbles].slice(-3)){const a=this.residents.get(id);if(a)this.drawBubble(c,a,b);}
  // Furniture labels are physical interaction targets, not invented wall content.
  this.plaque(c,1045,258,'RESEARCH WALL',{kind:'wall'});
  this.plaque(c,1210,261,'RABBIT HOLES',{kind:'holes'});
  if(this.snapshot?.conversations.length)this.plaque(c,800,620,`${this.snapshot.conversations.length} CONVERSATION${this.snapshot.conversations.length===1?'':'S'}`,{kind:'conversations'});
  const vignette=c.createRadialGradient(768,500,340,768,500,1000);vignette.addColorStop(0,'#00100a00');vignette.addColorStop(1,'#07161080');c.fillStyle=vignette;c.fillRect(0,0,W,H);
 }
 drawResident(c,id,a,t){
  const idx=CAST.indexOf(id.replace('agent_',''));if(idx<0)return;
  const f=this.frames[idx];const scale=.84+(a.y-320)/2100;const h=154*scale,w=h*f.w/f.h;
  const motion=a.replayMotion??a.card.motion;const bubble=this.bubbles.get(id);const talk=Boolean(bubble);const time=this.reduce?0:t;
  const bounce=a.walking?Math.abs(Math.sin(time*8+a.phase))*3:Math.sin(time*1.8+a.phase)*.75;
  const tilt=a.walking?Math.sin(time*8)*.025:talk?Math.sin(time*4+a.phase)*.018:motion==='listen'?Math.sin(time*2.5+a.phase)*.012:motion==='write'||motion==='work'?.025:0;
  c.save();c.translate(a.x,a.y);c.fillStyle='#050e0ba0';c.beginPath();c.ellipse(0,0,w*.4,8,0,0,Math.PI*2);c.fill();
  if(this.selected===id){c.strokeStyle=COLORS[idx];c.lineWidth=1.5;c.beginPath();c.ellipse(0,0,w*.55,12,0,0,Math.PI*2);c.stroke();}
  c.scale(a.face,1);c.rotate(tilt);c.drawImage(this.atlas,f.x,f.y,f.w,f.h,-w/2,-h-bounce,w,h);c.restore();
  this.hit.push({kind:'agent',id,x:a.x-w/2,y:a.y-h,w,h:h+24});
 }
 drawLabel(c,id,a){
  const idx=CAST.indexOf(id.replace('agent_',''));if(idx<0)return;
  const scale=.84+(a.y-320)/2100,h=154*scale,w=h*this.frames[idx].w/this.frames[idx].h;
  const fontSize=Math.max(14,12/this.scale);c.font=`500 ${fontSize}px system-ui`;const tw=c.measureText(a.card.name).width;
  c.fillStyle='#10211de0';c.beginPath();c.roundRect(a.x-tw/2-9,a.y+11,tw+18,23,4);c.fill();c.fillStyle=COLORS[idx];c.textAlign='center';c.fillText(a.card.name,a.x,a.y+27);
  if(a.thoughtUntil>performance.now()||a.findingUntil>performance.now()||a.founderUntil>performance.now()||a.card.current_research_id||a.card.motion==='message'){
   const icon=a.founderUntil>performance.now()?'✉':a.findingUntil>performance.now()?'◇':a.card.current_research_id?'⌕':a.card.motion==='message'?'✉':'○';
   c.fillStyle='#cee5cd';c.font='24px Georgia';c.fillText(icon,a.x+w/2+10,a.y-h+22);
  }
 }
 drawWall(c){
  const colors={QUESTION:'#ddd4a8',FINDING:'#dfc998',SOURCE:'#a8c1ac',HYPOTHESIS:'#bac6b2',DISAGREEMENT:'#c99078',CONNECTION:'#9bc8bc',MYSTERY:'#beb2c7'};
  for(const [i,p]of (this.snapshot?.wall??[]).slice(0,12).entries()){
   const x=962+(i%4)*44,y=103+Math.floor(i/4)*36;c.save();c.translate(x,y);c.rotate((i%3-1)*.04);c.fillStyle=colors[p.post_type]??'#dac49a';c.fillRect(0,0,36,28);c.fillStyle='#66563e';c.beginPath();c.arc(18,3,1.8,0,7);c.fill();c.restore();this.hit.push({kind:'post',post:p,x,y,w:36,h:28});
  }
  for(const[i,h]of(this.snapshot?.holes??[]).slice(0,8).entries()){
   const x=1181+(i%2)*30,y=145+Math.floor(i/2)*21;c.fillStyle={HOT:'#d89069',NEW:'#d9ceac',ACTIVE:'#98beaa',COOLING:'#a3b8bf',DORMANT:'#7c8176',RESOLVED:'#9aaf72',ABANDONED:'#706c64'}[h.status]??'#a9b7a1';c.fillRect(x,y,23,15);this.hit.push({kind:'hole',id:h.id,x,y,w:23,h:15});
  }
 }
 drawAmbience(c,t){
  c.save();c.globalCompositeOperation='screen';
  for(const[x,y,r]of[[347,126,125],[1360,359,135],[175,485,140],[800,380,90]]){const light=c.createRadialGradient(x,y,0,x,y,r);light.addColorStop(0,`rgba(247,183,83,${.065+Math.sin(t*1.1+x)*.009})`);light.addColorStop(1,'rgba(247,183,83,0)');c.fillStyle=light;c.fillRect(x-r,y-r,r*2,r*2);}
  c.globalCompositeOperation='source-over';
  for(let i=0;i<24;i++){const x=230+(i*137)%1080+Math.sin(t*.15+i)*16,y=210+(i*71+t*3)%670;c.fillStyle=`rgba(229,216,175,${.12+Math.sin(t+i)*.06})`;c.beginPath();c.arc(x,y,1+(i%2)*.4,0,7);c.fill();}
  for(let i=0;i<4;i++){const k=(t*.16+i*.25)%1;c.strokeStyle=`rgba(236,226,209,${(1-k)*.19})`;c.lineWidth=2;c.beginPath();c.moveTo(373+Math.sin(k*9+i)*6,182-k*45);c.bezierCurveTo(366,160-k*40,386,151-k*40,376,141-k*35);c.stroke();}
  // Listening-corner record spindle: only an ambient visual, not an agent action.
  c.strokeStyle='#b89b5b70';c.lineWidth=1;c.beginPath();c.ellipse(50,594,19,8,0,t*.3,t*.3+1.3);c.stroke();c.restore();
 }
 plaque(c,x,y,text,hit){c.font='11px system-ui';c.textAlign='center';const w=c.measureText(text).width+18;c.fillStyle='#10201ddd';c.beginPath();c.roundRect(x-w/2,y-13,w,22,3);c.fill();c.fillStyle='#d1c397';c.fillText(text,x,y+2);this.hit.push({...hit,x:x-w/2,y:y-13,w,h:22});}
 drawBubble(c,a,b){
  const font=Math.max(16,13/this.scale);c.font=`${font}px Georgia`;const text=short(b.text),words=text.split(/\s+/);let lines=[''];
  for(const word of words){const i=lines.length-1,test=(lines[i]+' '+word).trim();if(c.measureText(test).width>235&&lines[i])lines.push(word);else lines[i]=test;}
  if(lines.length>2)lines=[lines[0],short(lines.slice(1).join(' '),Math.max(20,lines[0].length))];
  const w=Math.max(160,...lines.map(l=>c.measureText(l).width))+26,h=lines.length*(font+4)+30;
  const x=clamp(a.x-w/2,15,W-w-15),y=a.y-178-h;
  c.fillStyle=b.kind==='ASK_QUESTION'?'#e8ddba':'#f0e5cd';c.strokeStyle='#a8986a';c.lineWidth=1;c.beginPath();c.roundRect(x,y,w,h,8);c.fill();c.stroke();c.beginPath();c.moveTo(a.x-7,y+h);c.lineTo(a.x,y+h+9);c.lineTo(a.x+7,y+h);c.fill();
  c.textAlign='left';c.fillStyle='#527366';c.font='10px system-ui';c.fillText(a.card.name.toUpperCase()+(b.kind==='ASK_QUESTION'?' · QUESTION':''),x+13,y+16);c.fillStyle='#26372d';c.font=`${font}px Georgia`;lines.forEach((l,i)=>c.fillText(l,x+13,y+34+i*(font+4)));
  this.hit.push({...b.detail,x,y,w,h});
 }
}
