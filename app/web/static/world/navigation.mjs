// Asset-space coordinates only. No positions leave the browser.
export const W=1536, H=1024;
export const ZONES={
  espresso_counter:{label:'Espresso counter',spots:[[325,370],[405,380],[485,375],[270,415],[355,430],[440,435],[520,420],[555,370]]},
  bar:{label:'The bar',spots:[[270,365],[355,390],[445,400],[520,360],[230,425],[305,460],[400,465],[500,470]]},
  communal_table:{label:'Communal table',spots:[[705,420],[820,420],[940,425],[1035,510],[1020,615],[880,635],[765,635],[600,555]]},
  couch:{label:'The lounge',spots:[[235,590],[360,600],[510,605],[620,695],[530,790],[390,815],[250,810],[605,805]]},
  research_computer:{label:'Research computer',spots:[[1225,505],[1160,530],[1190,445],[1140,455],[1125,580],[1215,605],[1070,435],[1080,530]]},
  zine_desk:{label:'Zine desk',spots:[[1300,605],[1220,650],[1160,660],[1245,710],[1150,725],[1090,655],[1090,755],[1210,765]]},
  recording_desk:{label:'Recording desk',spots:[[1310,780],[1230,810],[1170,820],[1330,890],[1215,905],[1130,905],[1280,955],[1390,950]]},
  phone:{label:'Roxy’s switchboard',spots:[[1250,420],[1180,405],[1110,405],[1280,475],[1200,480],[1145,485],[1060,380],[1130,350]]},
  research_wall:{label:'Research wall',spots:[[1005,350],[1085,350],[1160,345],[960,320],[1030,405],[1110,415],[1190,390],[1215,340]]},
  chalkboard:{label:'Chalkboard',spots:[[995,325],[1060,355],[930,345],[1090,405],[1160,360],[1000,415],[1200,410],[1150,440]]},
  bookshelf:{label:'Bookshelves',spots:[[150,435],[160,505],[220,480],[225,550],[285,505],[1000,345],[1080,340],[1150,330]]},
  windows:{label:'Forest windows',spots:[[600,330],[670,340],[740,340],[815,330],[875,340],[590,390],[665,395],[855,395]]},
  front_door:{label:'Front door',spots:[[210,340],[245,380],[170,380],[210,430],[290,345],[160,435],[305,410],[275,465]]},
  back_door:{label:'Back door',spots:[[1290,350],[1240,390],[1180,375],[1270,430],[1160,425],[1090,380],[1350,360],[1310,470]]},
  performance_corner:{label:'Listening corner',spots:[[120,625],[120,730],[145,835],[205,910],[290,915],[345,945],[405,935],[475,920]]},
};
export const OBSTACLES=[{x:640,y:480,w:350,h:110},{x:150,y:625,w:420,h:130}];
const blocked=(x,y)=>OBSTACLES.some(o=>x>o.x-12&&x<o.x+o.w+12&&y>o.y-12&&y<o.y+o.h+12);
const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
function visible(a,b){const steps=Math.ceil(distance(a,b)/6);for(let i=1;i<steps;i++)if(blocked(a[0]+(b[0]-a[0])*i/steps,a[1]+(b[1]-a[1])*i/steps))return false;return true;}
export function route(start,end){
  if(visible(start,end))return [end];
  const nodes=[start,end,...OBSTACLES.flatMap(o=>[[o.x-20,o.y-20],[o.x+o.w+20,o.y-20],[o.x-20,o.y+o.h+20],[o.x+o.w+20,o.y+o.h+20]])];
  const costs=nodes.map(()=>Infinity), previous=[], todo=new Set(nodes.map((_,i)=>i));costs[0]=0;
  while(todo.size){const current=[...todo].sort((a,b)=>costs[a]-costs[b])[0];todo.delete(current);if(current===1||!Number.isFinite(costs[current]))break;
    for(const i of todo)if(visible(nodes[current],nodes[i])){const cost=costs[current]+distance(nodes[current],nodes[i]);if(cost<costs[i]){costs[i]=cost;previous[i]=current;}}
  }
  if(!Number.isFinite(costs[1]))return []; // hold, never walk straight through a blocked path
  const path=[];let i=1;while(i!==0){path.unshift(nodes[i]);i=previous[i];}return path;
}
export function allocate(agents, previous=new Map()){
  const occupied=[]; const output=new Map();
  for(const a of agents){
    const location=a.visual_location??a.current_location;const zone=ZONES[location];if(!zone)continue;
    const prior=previous.get(a.agent_id);
    const free=spot=>!blocked(...spot)&&occupied.every(other=>distance(spot,other)>39);
    const spot=prior&&prior.zone===location&&free(prior.spot)?prior.spot:zone.spots.find(free);
    if(!spot)continue;
    occupied.push(spot);output.set(a.agent_id,{zone:location,spot});
  }
  return output;
}
