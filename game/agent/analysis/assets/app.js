'use strict';
const $ = id => document.getElementById(id);
const names = {combat:'Combat',selection:'Card selection',card_reward:'Card rewards',route:'Route',rewards:'Rewards',shop:'Shop',rest:'Rest site',event:'Events',ancient:'Ancient',treasure:'Treasure',relic_choice:'Relic choice',act_transition:'Act boundary'};
const colors = {combat:'#567765',selection:'#a9543c',card_reward:'#a1864b',route:'#648090',rewards:'#b8a584',shop:'#8a789d',rest:'#8caa7d',event:'#919b92'};
const fmt = (n, digits=0) => n == null ? '—' : (Number(n)===0?0:Number(n)).toLocaleString(undefined,{maximumFractionDigits:digits});
const human = text => String(text ?? '').replaceAll('_',' ');
const short = text => String(text || '').slice(0,8);
const empty = text => el('div',{class:'empty'},text);
function el(tag, attributes={}, ...children) {
  const node = document.createElement(tag);
  for (const [key,value] of Object.entries(attributes)) {
    if (key.startsWith('on')) node.addEventListener(key.slice(2),value);
    else if (key === 'class') node.className=value;
    else if (key === 'style') Object.assign(node.style,value);
    else if (value != null) node.setAttribute(key,String(value));
  }
  node.append(...children.flat(Infinity).filter(x=>x!=null).map(x=>x instanceof Node ? x : document.createTextNode(String(x))));
  return node;
}
function set(id,...children) { $(id).replaceChildren(...children.flat().filter(x=>x!=null)); }
function badge(text,kind='') { return el('span',{class:'badge '+kind},text); }
function stat(label,value) { return el('div',{class:'state-stat'},label,el('b',{},value)); }
function error(message) { $('error').textContent=message; $('error').hidden=!message; }
async function api(route) {
  const response = await fetch('/api/'+route,{cache:'no-store'});
  const value=await response.json();
  if (!response.ok) throw new Error(value.error || 'Unable to load recording');
  return value;
}
let report, run, decision, comparison, view='overview', sequence=0;
function switchView(name,autoload=true) {
  view=name;
  for(const button of document.querySelectorAll('nav button')) button.classList.toggle('active',button.dataset.view===name);
  for(const n of ['overview','inspector','training']) $(n+'-view').hidden=n!==name;
  if(autoload&&name==='inspector'&&!run) {
    const choice=filteredRuns().find(r=>r.flag_counts.warning) || filteredRuns()[0] || report.runs[0];
    if(choice) openRun(choice.id);
  }
}
function filteredRuns() {
  const split=$('split').value,evidence=$('evidence').value,policy=$('policy').value,query=$('search').value.toLowerCase();
  return report.runs.filter(r=>(split==='all'||r.metadata.split===split) && (evidence==='all'||r.metadata.evidence===evidence)
    && (policy==='all'||r.policy===policy) && [r.id,r.case_id,r.policy,r.status,r.goal].join(' ').toLowerCase().includes(query));
}
function metric(label,value,note,kind='') { return el('div',{class:'metric '+kind},el('div',{class:'metric-name'},label),el('div',{class:'metric-number'},value),el('div',{class:'metric-note'},note)); }
function outcome(r) { return r.status==='success' ? (r.goal==='act1'?'Act 1 cleared':'Run victory') : r.status==='cutoff'?'Cutoff · '+human(r.outcome.reason):human(r.status); }
function renderOverview() {
  const runs=filteredRuns(),steps=runs.reduce((s,r)=>s+r.steps,0),act=runs.filter(r=>r.goal==='act1');
  const groups=new Map(),categories={};
  for(const r of runs) {
    // Distinct source implementations/objectives/evidence/splits are never pooled in a policy rate.
    const key=JSON.stringify([r.policy,r.goal,r.metadata.split,r.metadata.evidence,r.metadata.build,r.metadata.rules,r.training?.reward_identity,r.training?.collection_id||r.metadata.policy]);
    if(!groups.has(key)) groups.set(key,[]);
    groups.get(key).push(r);
    for(const [category,count] of Object.entries(r.categories)) categories[category]=(categories[category]||0)+count;
  }
  set('metrics',metric('Act 1 completions',`${act.filter(r=>r.act1_cleared).length} / ${act.length}`,'Recorded Act 1 episodes in this view','green'),
    metric('Recorded decisions',fmt(steps),`${runs.length} verified trajectories`),
    metric('Last observed floor',fmt(runs.length ? runs.reduce((s,r)=>s+(r.last_hud?.floor||0),0)/runs.length:null,1),'Mean public HUD · not distance to victory'),
    metric('Runs with loop signals',runs.filter(r=>r.flag_counts.warning).length,'Selection or reward navigation to review','rust'));
  set('policy-rows',[...groups.values()].map(rows=>{
    const r=rows[0],success=rows.filter(r=>r.task_success).length;
    return el('tr',{},el('td',{},el('span',{class:'policy-name'},el('i',{class:'policy-dot'}),r.policy),el('span',{class:'muted'},`${r.goal||'Goal unlabelled'} · ${r.metadata.split} · ${human(r.metadata.evidence)}`),el('span',{class:'muted mono'},`source ${short(r.metadata.build)} · rules ${short(r.metadata.rules)}`)),
      el('td',{},r.goal?`${success} / ${rows.length}`:'—'),el('td',{},fmt(rows.reduce((s,x)=>s+(x.last_hud?.floor||0),0)/rows.length,1)),
      el('td',{},rows.filter(x=>x.status==='cutoff').length),el('td',{},rows.reduce((s,x)=>s+x.flag_counts.warning,0)));
  }));
  if(!groups.size) set('policy-rows',el('tr',{},el('td',{colspan:5},'No runs match these filters.')));
  const max=Math.max(1,...Object.values(categories));
  set('category-bars',Object.entries(categories).sort((a,b)=>b[1]-a[1]).map(([key,count])=>el('div',{class:'bar-row'},names[key]||human(key),el('div',{class:'bar-track'},el('div',{class:'bar-fill',style:{width:(100*count/max)+'%',background:colors[key]||'#919b92'}})),el('span',{class:'bar-count'},fmt(count)))));
  $('run-count').textContent=`/ ${runs.length}`;
  set('run-rows',runs.map(r=>el('tr',{},el('td',{},el('button',{class:'link-button',onclick:()=>openRun(r.id)},'↗ '+short(r.id)),el('span',{class:'muted mono'},r.case_id?'case '+short(r.case_id):r.metadata.split)),
    el('td',{},r.policy),el('td',{},badge(outcome(r),r.status)),el('td',{},fmt(r.last_hud?.floor)),el('td',{},fmt(r.steps)),
    el('td',{},r.flag_counts.warning?badge(`${r.flag_counts.warning} loop signal${r.flag_counts.warning>1?'s':''}`,'warning'):el('span',{class:'muted'},`${r.flag_counts.info} informational`)))));
  $('pending').textContent=report.pending.length ? `${report.pending.length} planned episode(s) have no completed recording (failed, interrupted or unattempted). They remain listed in provenance. Rates above use recorded episodes only; this is not a complete planned evaluation rate.` : report.sources.length?'All episodes declared in the loaded evaluation and PPO reports have completed recordings.':'No evaluation or PPO plan was loaded. This view describes the supplied recordings only.';
  $('review-flags').disabled=!runs.some(r=>r.flag_counts.warning);
}
async function openRun(id,step=null) {
  const token=++sequence;
  error(''); switchView('inspector',false);
  $('run-title').textContent='Loading run…';
  try {
    const loaded=await api('run?id='+encodeURIComponent(id));
    if(token!==sequence)return;
    run=loaded; decision=null; comparison=null;
    document.querySelector('.decision-main').hidden=!run.steps;
    $('run-title').textContent=`${run.policy} / ${short(run.id)}`;
    $('run-subtitle').textContent=`${run.metadata.split} · ${human(run.metadata.evidence)} · ${run.goal==='act1'?'Act 1 goal':run.goal==='full_run'?'Campaign goal':'Goal not recorded'} · ${run.case_id?'paired case '+short(run.case_id):run.metadata.scenario}`;
    $('run-select').value=id;
    set('run-summary',badge(outcome(run),run.status),el('span',{},el('strong',{},fmt(run.steps)),' decisions'),el('span',{},'Last floor ',el('strong',{},fmt(run.last_hud?.floor))),el('span',{},'Canonical outcome: ',el('strong',{},human(run.outcome.kind)+' / '+human(run.outcome.reason))),el('span',{},'Canonical return: ',el('strong',{},run.canonical_return)));
    set('category',el('option',{value:'all'},'All categories'),Object.keys(run.categories).map(key=>el('option',{value:key},names[key]||human(key))));
    set('rooms',run.rooms.map(room=>el('button',{class:'room',title:`Act ${room.act}, floor ${room.floor}: ${room.contexts.join(', ')}`,onclick:()=>chooseStep(room.start)},el('span',{class:'room-label'},`ACT ${room.act}`),el('span',{class:'floor'},room.floor),el('span',{class:'room-label'},(names[room.contexts[0]]||human(room.contexts[0])).slice(0,12)))));
    renderFlags();
    if(run.steps) await chooseStep(step==null?(run.flags.find(f=>f.level==='warning')?.start||0):Math.min(run.steps-1,Math.max(0,step)));
    else {set('decision-list',empty('No actions recorded.'));set('state-content',empty('The recording ended before a decision.'));set('actions-body');$('decision-title').textContent='No recorded decisions';$('compare').disabled=true;}
  } catch(e) { if(token===sequence)error(e.message); }
}
function renderFlags() {
  function link(flag) { return el('button',{class:'flag-link',title:flag.reason,onclick:()=>chooseStep(flag.start)},human(flag.kind),el('span',{class:'muted'},`Steps ${flag.start+1}–${flag.end+1}`)); }
  const warning=run.flags.filter(f=>f.level==='warning'),info=run.flags.filter(f=>f.level==='info');
  set('flags',warning.map(link),info.length?el('details',{},el('summary',{},`${info.length} informational signals`),info.map(link)):null);
}
function renderDecisionList() {
  const cat=$('category').value,rows=run.timeline.filter(r=>cat==='all'||r.category===cat),selected=decision?.step??0;
  let center=rows.findIndex(r=>r.step>=selected); if(center<0)center=rows.length-1;
  const first=Math.max(0,Math.min(center-10,rows.length-40)),visible=rows.slice(first,first+40);
  set('decision-list',visible.map(r=>el('button',{class:'decision-row'+(selected===r.step?' active':''),onclick:()=>chooseStep(r.step)},
    el('span',{class:'row-top'},`#${r.step+1} · F${r.floor}`,el('span',{},names[r.category]||human(r.category))),el('span',{class:'row-title'},r.label))),
    rows.length>40?el('div',{class:'window-note'},`Showing ${first+1}–${first+visible.length} of ${rows.length}. Use step number, slider or floor timeline to jump.`):null);
}
function entity(node) {
  const summary=Object.entries(node.fields).filter(([k,v])=>v!=null&&v!==false&&v!==0).map(([k,v])=>`${human(k)}: ${v}`).join(' · ');
  const brief=Object.entries(node.fields).filter(([k,v])=>v!=null&&['hp','max_hp','block','energy','minimum','maximum','count','row','column','price'].includes(k)).map(([k,v])=>`${human(k)} ${v}`).join(' · ');
  const intent=node.children.find(n=>n.kind==='intent');
  const intentText=intent?`${intent.name} · ${Object.entries(intent.fields).map(([k,v])=>`${human(k)} ${v}`).join(' · ')}`:'';
  return el('details',{class:'entity'},el('summary',{},node.name||human(node.kind),brief?el('span',{class:'entity-sub'},brief):null,intentText?el('span',{class:'entity-sub'},intentText):null,node.ref?el('span',{class:'entity-sub mono'},node.ref):null),
    el('div',{class:'entity-sub'},summary||'No scalar fields'),Object.keys(node.links).length?el('pre',{},JSON.stringify(node.links,null,2)):null,node.children.map(entity));
}
function mapGraph(map,data) {
  const nodes=map.children.filter(n=>n.kind==='node');
  if(!map.fields.available||!nodes.length)return el('div',{class:'map-empty'},'No map was available at this decision.');
  if(nodes.some(n=>!Number.isFinite(n.fields.row)||!Number.isFinite(n.fields.column)))
    return el('div',{},el('p',{},'This recording has no complete map layout.'),entity(map));
  const byRef=new Map(nodes.map(n=>[n.ref,n])),current=new Set(map.links.current||[]);
  // Legal route choices can include jumps that are not ordinary map connections.
  const available=new Set(data.candidates.filter(a=>a.kind==='choose_map_node').map(a=>a.subject));
  const chosen=data.action.kind==='choose_map_node'?data.action.subject:null;
  const symbols={Combat:'C',Elite:'E',Rest:'R',Shop:'$',Treasure:'T',Unknown:'?',Boss:'B',Ancient:'A',Event:'?'};
  const symbol=n=>symbols[n.name]||n.name.slice(0,1);
  const status=n=>[current.has(n.ref)?'Current room':null,n.fields.visited?'Visited':null,
    available.has(n.ref)?'Available now':null,n.ref===chosen?'Recorded choice':null].filter(Boolean);
  const label=n=>`${n.name} · row ${n.fields.row}, column ${n.fields.column}`;
  const ns=(tag,attrs={},text=null)=>{
    const n=document.createElementNS('http://www.w3.org/2000/svg',tag);
    for(const[k,v]of Object.entries(attrs))n.setAttribute(k,String(v));
    if(text!=null)n.textContent=text;
    return n;
  };
  const rows=[...new Set(nodes.map(n=>n.fields.row))].sort((a,b)=>a-b);
  const minCol=Math.min(...nodes.map(n=>n.fields.column)),maxCol=Math.max(...nodes.map(n=>n.fields.column));
  const width=560,height=80+(rows.at(-1)-rows[0])*40;
  const position=n=>[minCol===maxCol?width/2:64+(n.fields.column-minCol)/(maxCol-minCol)*(width-108),40+(rows.at(-1)-n.fields.row)*40];
  const svg=ns('svg',{class:'map-svg',viewBox:`0 0 ${width} ${height}`,role:'group','aria-label':`Act ${data.hud.act} map. Routes go from bottom to top.`});
  svg.append(ns('title',{},`Act ${data.hud.act} · recorded public map`),ns('desc',{},'Select a room to inspect its public details. Room colors show visited, current, available and recorded choices at this decision.'));
  for(const row of rows){
    const y=40+(rows.at(-1)-row)*40;
    svg.append(ns('line',{x1:43,x2:width-20,y1:y,y2:y,class:'map-guide'}),ns('text',{x:24,y:y+4,class:'map-row','text-anchor':'middle'},row));
  }
  svg.append(ns('text',{x:24,y:15,class:'map-row','text-anchor':'middle'},'ROW'));
  const edges=ns('g',{'aria-hidden':'true'});
  for(const node of nodes)for(const ref of node.links.next_nodes||[]){
    const next=byRef.get(ref);if(!next)continue;
    const [x1,y1]=position(node),[x2,y2]=position(next);
    const active=current.has(node.ref)&&available.has(ref);
    edges.append(ns('path',{d:`M ${x1} ${y1} L ${x2} ${y2}`,class:'map-edge'+(active?' available':'')+(active&&ref===chosen?' chosen':''),'data-from':node.ref,'data-to':ref}));
  }
  svg.append(edges);
  const details=el('div',{class:'map-room-details','aria-live':'polite'}),buttons=new Map();
  function inspect(node){
    for(const [ref,{button,group}]of buttons){
      button.setAttribute('aria-pressed',String(ref===node.ref));
      group.classList.toggle('inspected',ref===node.ref);
    }
    const marks=Object.entries(node.fields).filter(([key,value])=>key.endsWith('_marked')&&value).map(([key])=>human(key));
    details.replaceChildren(el('div',{class:'eyebrow'},'INSPECTED ROOM'),el('h3',{},node.name),
      el('p',{class:'mono'},node.ref),el('p',{},`Row ${node.fields.row} · column ${node.fields.column}`),
      el('p',{class:'map-room-status'},status(node).join(' · ')||'Not visited'),
      marks.length?el('p',{},marks.join(' · ')):document.createTextNode(''),
      el('h4',{},'Outgoing connections'),
      (node.links.next_nodes||[]).length?el('div',{class:'map-connections'},(node.links.next_nodes||[]).map(ref=>{
        const next=byRef.get(ref);
        return next?el('button',{onclick:()=>inspect(next),title:label(next)},`${next.name} · row ${next.fields.row}`,el('span',{class:'mono'},ref)):
          el('span',{class:'muted mono'},ref);
      })):el('p',{},'No outgoing connections.'),
      el('p',{class:'map-room-note'},'Room types reflect this recorded state. “?” remains unknown.'));
  }
  for(const node of nodes){
    const [x,y]=position(node),flags=status(node);
    const group=ns('g',{class:'map-node'+(node.fields.visited?' visited':'')+(current.has(node.ref)?' current':'')+
      (available.has(node.ref)?' available':'')+(node.ref===chosen?' chosen':''),transform:`translate(${x},${y})`,
      'data-ref':node.ref});
    group.append(ns('title',{},`${label(node)} · ${node.ref}${flags.length?' · '+flags.join(' · '):''}`),
      ns('rect',{class:'map-inspected',x:-19,y:-19,width:38,height:38,rx:7}),
      ns('circle',{class:'map-node-ring',r:16}),ns('circle',{class:'map-node-dot',r:12}),
      ns('text',{'text-anchor':'middle',y:4},symbol(node)));
    if(node.fields.fur_coat_marked||node.fields.spoils_map_marked)group.append(ns('circle',{class:'map-mark',cx:12,cy:-12,r:3}));
    // Native buttons give every room a full hit area and standard keyboard activation.
    const hit=ns('foreignObject',{x:-19,y:-19,width:38,height:38});
    const button=el('button',{class:'map-hit',type:'button','aria-label':`${label(node)}${flags.length?' · '+flags.join(' · '):''}`,
      'aria-pressed':'false',title:`${label(node)} · ${node.ref}`,onclick:()=>inspect(node)});
    hit.append(button);group.append(hit);buttons.set(node.ref,{button,group});svg.append(group);
  }
  inspect(byRef.get(chosen)||nodes.find(n=>current.has(n.ref))||nodes[0]);
  const types=[...new Map(nodes.map(n=>[n.name,n])).values()];
  return el('section',{class:'map-panel','aria-label':'Recorded map'},
    el('div',{class:'map-heading'},el('div',{},el('h3',{},`Act ${data.hud.act} map`),el('p',{},'↑ Routes climb from bottom to top. Click a room to inspect it.')),
      el('span',{class:'muted'},`${nodes.filter(n=>n.fields.visited).length} / ${nodes.length} rooms visited`)),
    el('div',{class:'map-legend'},[['current','Current room'],['visited','Visited'],['available','Available now'],['chosen','Recorded choice']].map(([kind,text])=>
      el('span',{},el('i',{class:'map-key '+kind,'aria-hidden':'true'}),text))),
    el('div',{class:'map-body'},el('div',{class:'map-canvas'},svg),el('aside',{class:'map-aside'},details,
      el('div',{class:'map-types'},el('h4',{},'Room types'),types.map(n=>el('span',{},el('b',{},symbol(n)),n.name))))),
    el('details',{class:'map-raw'},el('summary',{},'Raw map details'),entity(map)));
}
function showState(data) {
  const ctx=data.context_view,combat=ctx.kind==='combat';
  const hud=data.hud,stats=[stat('HP',`${hud.hp} / ${hud.max_hp}`),stat('Gold',fmt(hud.gold)),stat('Act / floor',`${hud.act} / ${hud.floor}`)];
  if(combat)stats.push(stat('Energy',fmt(ctx.fields.energy)),stat('Block',fmt(ctx.fields.block)),stat('Round',fmt(ctx.fields.round)));
  set('state-stats',stats);
  if(combat) {
    const hand=ctx.children.find(n=>n.kind==='pile'&&n.name.toLowerCase()==='hand');
    const enemies=ctx.children.find(n=>n.kind==='enemies');
    const selections=ctx.children.filter(n=>n.kind==='selection');
    set('state-content',el('div',{class:'state-block'},el('h4',{},'HAND · public cards'),hand?.children.length?hand.children.map(entity):el('p',{},'No cards in hand.'),selections.map(entity)),
      el('div',{class:'state-block'},el('h4',{},'ENEMIES · visible intent'),enemies?.children.map(entity),el('details',{},el('summary',{class:'muted'},'Piles, powers, resources & full context'),ctx.children.filter(n=>n!==hand&&n!==enemies&&!selections.includes(n)).map(entity))));
  } else set('state-content',ctx.kind==='map'?null:el('div',{class:'state-block state-wide'},el('h4',{},(names[ctx.kind]||human(ctx.kind)).toUpperCase()),entity(ctx)));
  $('state-content').append(el('div',{class:'state-block state-wide'},el('h4',{},'RUN INVENTORY & MAP'),
    el('div',{class:'run-inventory'},data.inventory.filter(n=>n.kind!=='map').map(entity)),data.inventory.filter(n=>n.kind==='map').map(n=>mapGraph(n,data))));
  const delta=Object.entries({...data.delta,...data.combat_delta}).map(([key,value])=>`${human(key)} ${value>0?'+':''}${value}`);
  for(const enemy of data.enemy_changes||[])if(enemy.before_hp!==enemy.after_hp)delta.push(`${enemy.name} HP ${enemy.before_hp} → ${enemy.after_hp}`);
  set('transition',el('strong',{},'Observed result: '),data.terminal?`Canonical ${human(data.terminal.kind)}. Terminal HP is not present in the canonical outcome.`:delta.join(' · '),
    data.after_hud?` · next context: ${human(data.successor.context.kind)}`:'',el('br'),`Canonical reward ${data.canonical_reward}. Net HP change includes healing; no damage total is inferred.`);
}
async function chooseStep(step) {
  if(!run||!run.steps)return;
  step=Math.min(run.steps-1,Math.max(0,Math.floor(Number(step)||0)));
  const id=run.id,token=++sequence;
  comparison=null; error(''); $('compare').disabled=true;
  try {
    const value=await api(`decision?id=${encodeURIComponent(id)}&step=${step}`);
    if(token!==sequence||run.id!==id)return;
    decision=value;
    const row=run.timeline[step];
    $('decision-category').textContent=`${names[row.category]||human(row.category)} / FLOOR ${row.floor}`;
    $('decision-title').textContent=row.label;
    $('step-number').value=step+1;$('step-number').max=run.steps;$('step-slider').max=run.steps-1;$('step-slider').value=step;
    $('previous').disabled=step===0;$('next').disabled=step===run.steps-1;
    [...$('rooms').children].forEach((button,i)=>button.classList.toggle('active',run.rooms[i].start<=step&&run.rooms[i].end>=step));
    renderDecisionList();showState(value);renderActions();renderLearner();
    $('raw-state').textContent=JSON.stringify(value.observation,null,2);
    $('provenance').textContent=`Trajectory ${run.sha256}\nState ${value.state_sha256}\nRecorded policy ${run.metadata.policy}\nBuild ${run.metadata.build}\nRules ${run.metadata.rules}`;
    $('compare').disabled=!report.models.length;
    $('compare').textContent=report.models.length?'Compare checkpoints':'No checkpoints loaded';
    history.replaceState(null,'',`#run=${id}&step=${step}`);
  }catch(e){if(token===sequence)error(e.message);}
}
function renderActions() {
  if(!decision)return;
  const models=comparison?.models||[];
  set('actions-head',el('tr',{},el('th',{},'Native legal action'),models.map(m=>el('th',{},m.label)),!models.length?el('th',{},'Policy preference'):null));
  const sorted=[...decision.candidates];
  const refs=new Map();
  function visit(n){if(n.ref)refs.set(n.ref,n);n.children.forEach(visit);}
  visit(decision.context_view);decision.inventory.forEach(visit);
  if(models.length) {
    const lookup=new Map(models[0].probabilities.map(p=>[p.ref,p.probability]));
    sorted.sort((a,b)=>lookup.get(b.ref)-lookup.get(a.ref));
  }
  set('actions-body',sorted.map(action=>el('tr',{class:action.ref===decision.action.ref?'recorded':''},el('td',{},action.label,
    el('span',{class:'muted mono'},action.ref),action.ref===decision.action.ref?el('span',{class:'recorded-mark'},'RECORDED ACTION'):null,
    action.subject||action.target?el('details',{},el('summary',{class:'muted'},'Choice details'),[action.subject,action.target].filter(ref=>refs.has(ref)).map(ref=>entity(refs.get(ref)))):null),
    models.map((m,index)=>{const p=m.probabilities.find(p=>p.ref===action.ref),only=m.probabilities.filter(p=>p.allowed).length===1;return el('td',{class:'prob'},p.allowed?el('span',{class:'prob-number'},fmt(100*p.probability,2)+'%'):el('span',{class:'prob-excluded'},'Policy excluded'),p.allowed?el('div',{class:'bar-track'},el('div',{class:'bar-fill',style:{width:100*p.probability+'%',background:index%2?'#a1864b':'#567765'}})):null,only&&p.allowed?el('span',{class:'muted'},'Only policy-allowed action'):null);}),
    !models.length?el('td',{class:'muted'},'Not recomputed'):null)));
  set('model-notes',models.map(m=>el('div',{class:'model-note'},el('strong',{},m.label),el('span',{class:'muted'},`Critic ${fmt(m.value,4)} · shaped ${m.reward_spec.goal||m.reward_spec.schema} return`),el('span',{class:'muted'},m.matches_recorded_policy?'Matches recorded policy identity':'Different from recorded policy'),el('span',{class:'muted mono'},m.identity),el('span',{class:'muted'},`Action policy: ${m.action_policy}`))));
  const different=new Set(models.map(m=>m.reward_identity)).size>1;
  $('comparison-note').textContent=models.length?`${comparison.interpretation}${different?' These checkpoints use different reward objectives; their critic values are not directly comparable.':''}`:
    report.models.length?'Compare to rank these legal actions under each loaded checkpoint. This does not replay alternative outcomes.':'To enable probabilities, restart the viewer with --checkpoint label=path.sts-model. Recorded choices and public states work without training dependencies.';
}
function renderLearner() {
  const data=decision.training;$('learner-panel').hidden=!data;
  if(!data)return;
  set('learner-data',el('div',{class:'learner-grid'},stat('Chosen action probability',fmt(100*data.chosen_probability,2)+'%'),stat('Recorded critic',fmt(data.value,4)),stat('Training reward',fmt(data.reward,4)),stat('Recorded advantage',fmt(data.advantage,4))),
    el('div',{class:'note'},`Return target ${fmt(data.return,4)} · next value ${fmt(data.next_value,4)} · ${data.terminated?'task terminal':data.truncated?'task truncated':'continuing'}. Rewards recomputed and matched to public measurements; learner diagnostics are recorded values, not independently reproduced inference.`),
    el('div',{class:'table-wrap'},el('table',{},el('thead',{},el('tr',{},el('th',{},'Reward component'),el('th',{},'Measured'),el('th',{},'Weight'),el('th',{},'Contribution'))),el('tbody',{},Object.entries(data.components).map(([key,value])=>el('tr',{},el('td',{},human(key)),el('td',{},fmt(value,4)),el('td',{},fmt(run.training.reward_spec.weights[key]||0,4)),el('td',{},fmt(value*(run.training.reward_spec.weights[key]||0),4))))))));
}
async function compare() {
  if(!decision||!report.models.length)return;
  const token=sequence,id=run.id,step=decision.step;
  $('compare').disabled=true;$('compare').textContent='Scoring this state…';error('');
  try {const value=await api(`compare?id=${id}&step=${step}`);if(token===sequence){if(value.state_sha256!==decision.state_sha256)throw new Error('Comparison state mismatch');comparison=value;renderActions();}}
  catch(e){if(token===sequence)error(e.message);}
  finally{if(token===sequence){$('compare').disabled=false;$('compare').textContent='Recompute comparison';}}
}
function chart(iterations,key,color) {
  const points=iterations.filter(i=>i[key]!=null),values=points.map(i=>i[key]);
  if(!points.length)return empty('No completed updates.');
  const min=Math.min(0,...values),max=Math.max(key==='clears'?1:1e-6,...values),span=max-min||1;
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 500 160');svg.setAttribute('role','img');svg.setAttribute('aria-label',`${human(key)} by cumulative collected decisions`);
  const ns=(tag,attrs)=>{const n=document.createElementNS(svg.namespaceURI,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);return n;};
  for(let i=0;i<4;i++)svg.append(ns('line',{x1:38,y1:15+i*35,x2:488,y2:15+i*35,stroke:'#e5e6df'}));
  const coords=points.map(p=>[38+450*p.decisions/points.at(-1).decisions,120-100*(p[key]-min)/span]);
  svg.append(ns('polyline',{points:coords.map(p=>p.join(',')).join(' '),fill:'none',stroke:color,'stroke-width':2}));
  coords.forEach(([x,y],i)=>{const dot=ns('circle',{cx:x,cy:y,r:3,fill:color});const title=ns('title',{});title.textContent=`${points[i].decisions} decisions: ${points[i][key]}`;dot.append(title);svg.append(dot);});
  for(const [x,y,label]of[[0,19,fmt(max,2)],[0,123,fmt(min,2)],[38,150,'0'],[440,150,fmt(points.at(-1).decisions)]]){const text=ns('text',{x,y,fill:'#747971','font-size':10});text.textContent=label;svg.append(text);}
  return el('div',{class:'chart'},svg,el('div',{class:'chart-label'},el('span',{},'Cumulative collected decisions'),el('span',{},human(key))));
}
function renderTraining() {
  if(!report.training.length){set('training-content',empty('No full-run PPO reports were included. Add the public PPO output directory when building the analysis export.'));return;}
  set('training-content',report.training.map(job=>el('section',{class:'panel'},el('div',{class:'panel-heading'},el('h3',{},job.label),badge(job.status)),
    el('div',{class:'training-grid'},el('div',{},el('div',{class:'panel-heading'},el('h3',{},'Mean collection return')),chart(job.iterations,'mean_return','#567765')),el('div',{},el('div',{class:'panel-heading'},el('h3',{},'Act 1 clears per rollout')),chart(job.iterations,'clears','#a9543c'))),
    el('div',{class:'table-wrap'},el('table',{},el('thead',{},el('tr',{},['Iteration','Decisions','Episodes','Act 1 clears','Cutoffs','Mean return','Update'].map(x=>el('th',{},x)))),el('tbody',{},job.iterations.map(i=>el('tr',{},[i.iteration,fmt(i.decisions),i.episodes,i.clears,i.cutoffs,fmt(i.mean_return,4),human(i.update_status)].map(x=>el('td',{},x))))))),
    el('details',{class:'training-objective'},el('summary',{},`Reward objective · ${job.reward_spec.goal||job.reward_spec.schema}`),el('pre',{class:'mono'},JSON.stringify(job.reward_spec,null,2)),el('p',{},'Collection performance changes with sampled starts. Compare held-out evaluations on matching cases before claiming improvement.')))));
}
function resetFilters(){ $('split').value=report.runs.some(r=>r.metadata.split==='validation')?'validation':report.runs[0]?.metadata.split||'all';$('evidence').value=report.runs.some(r=>r.metadata.evidence==='headless_rollout')?'headless_rollout':'all';$('policy').value='all';$('search').value='';renderOverview(); }
async function start() {
  try {
    report=await api('report');$('title').textContent=report.title;document.title=report.title+' · StS agent';
    $('dataset-label').textContent=`${report.runs.length} RUNS / ${report.paired_cases_verified} PAIRED CASES`;
    set('policy',el('option',{value:'all'},'All policies'),[...new Set(report.runs.map(r=>r.policy))].sort().map(p=>el('option',{value:p},p)));
    set('run-select',report.runs.map(r=>el('option',{value:r.id},`${r.policy} · ${short(r.id)} · ${r.metadata.split} · ${outcome(r)}`)));
    set('limitations',report.limitations.map(s=>el('p',{},s)),el('p',{},`Exported ${report.created_at}. Verification and export: ${fmt(report.build_seconds,1)} s. Each public decision chunk is digest-checked when loaded.`),
      report.pending.length?el('pre',{class:'mono'},JSON.stringify(report.pending,null,2)):null);
    for(const button of document.querySelectorAll('nav button'))button.addEventListener('click',()=>switchView(button.dataset.view));
    for(const id of ['split','evidence','policy'])$(id).addEventListener('change',renderOverview);
    $('search').addEventListener('input',renderOverview);$('clear-filters').addEventListener('click',resetFilters);
    $('review-flags').addEventListener('click',()=>{const selected=filteredRuns().find(r=>r.flag_counts.warning);if(selected)openRun(selected.id);});
    $('run-select').addEventListener('change',e=>openRun(e.target.value));$('category').addEventListener('change',renderDecisionList);
    $('previous').addEventListener('click',()=>chooseStep(decision.step-1));$('next').addEventListener('click',()=>chooseStep(decision.step+1));
    $('step-number').addEventListener('change',e=>chooseStep(Number(e.target.value)-1));$('step-slider').addEventListener('change',e=>chooseStep(e.target.value));
    $('compare').addEventListener('click',compare);
    document.addEventListener('keydown',e=>{if(view!=='inspector'||!decision||['INPUT','SELECT','TEXTAREA','BUTTON'].includes(document.activeElement.tagName))return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();chooseStep(decision.step+(e.key==='ArrowRight'?1:-1));}});
    resetFilters();renderTraining();$('loading').hidden=true;$('main').hidden=false;
    function followHash(){
      const hash=new URLSearchParams(location.hash.slice(1)),id=hash.get('run'),step=Number(hash.get('step'))||0;
      if(id&&report.runs.some(r=>r.id===id)&&(run?.id!==id||decision?.step!==step))openRun(id,step);
    }
    window.addEventListener('hashchange',followHash);followHash();
  } catch(e){$('loading').hidden=true;error(e.message);}
}
start();
