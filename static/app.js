'use strict';
const $ = id => document.getElementById(id);
const canvas = $('canvas'), ctx = canvas.getContext('2d'), viewport = $('viewport');
let doc = null, west = [], south = [], overview = null, cell = 28, ox = 48, oy = 48;
let width = 1, height = 1, selected = null, history = [], busy = false, drag = null, frame = 0;
let inspectedTile = null;
const bandSize=36;
let axisView='both', margin=bandSize*2, topPipes=[], coordinateMode='grid', lastInspection=null;
function axisBands(){return axisView==='both'?['pipe','edge']:[axisView];}
function axisValue(kind,axis,index){return kind==='pipe'?(axis==='x'?topPipes[index]:index+1):(axis==='x'?index+1:doc.n-index);}
function axisHit(x,y){
  if(!doc)return null;
  const axis=y>=0&&y<margin&&x>=margin?'x':x>=0&&x<margin&&y>=margin?'y':null;
  if(!axis)return null;
  const index=Math.floor(((axis==='x'?x:y)-(axis==='x'?ox:oy))/cell);
  if(index<0||index>=doc.n)return null;
  const kind=axisBands()[Math.floor((axis==='x'?y:x)/bandSize)];
  return {axis,kind,index,value:axisValue(kind,axis,index)};
}
function targetExit(p,n){return p<=2||p>=n-1?p:n+1-p;}
function selectedCoordinates(){
  const mode=$('coordinates').value||'grid';
  if(!['grid','pipe','edge'].includes(mode))throw new Error('Choose Grid, Black, or Blue turn coordinates.');
  return mode;
}
function convertTurns(turns,n,from,to){
  if(!Number.isInteger(n)||n<5||n>1000)throw new Error('N must be an integer between 5 and 1000.');
  if(!Array.isArray(turns))throw new Error('Turns must be an array of coordinate pairs.');
  return turns.map(point=>{
    if(!Array.isArray(point)||point.length!==2||point.some(v=>!Number.isInteger(v)||v<1||v>n))throw new Error('Coordinates must be integer pairs between 1 and N.');
    let [r,c]=point;
    if(from==='edge')r=n+1-r;
    if(from==='pipe')c=targetExit(c,n);
    return [to==='edge'?n+1-r:r,to==='pipe'?targetExit(c,n):c];
  });
}
function prescribedInput(){
  const input=generationInput();
  const mode=selectedCoordinates();
  const turns=convertTurns(JSON.parse($('turns').value),input.n,mode,'grid');
  if(turns.length!==5)throw new Error('Supply exactly five ordered turn coordinates.');
  // The first turn fixes the entrance row; a previous pipe selection must not
  // override the path, especially when Y is a reversed blue edge label.
  const pipe=turns[0][0];
  $('pipe').value=pipe;coordinateMode=mode;
  return {...input,pipe,turns};
}
function updateEntranceFromTurns(){
  try{
    const turns=convertTurns(JSON.parse($('turns').value),Number($('n').value),selectedCoordinates(),'grid');
    if(turns.length)$('pipe').value=turns[0][0];
  }catch{/* Allow partially typed JSON; submission reports validation errors. */}
}
function tileLabels(r,c){return `Grid (${r+1}, ${c+1})\nBlack pipe axes (${r+1}, ${topPipes[c]||'boundary'})\nBlue edge axes (${doc.n-r}, ${c+1})`;}
function status(message, error = false) { $('status').textContent = message; $('status').className = error ? 'error' : ''; }
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
async function run(task) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('button').forEach(b => b.disabled = true);
  try { await task(); } catch (e) { status(e.message, true); }
  finally { busy = false; document.querySelectorAll('button').forEach(b => b.disabled = false); $('cancel-search').disabled=true; updateUndo(); }
}
function updateUndo() { $('undo').disabled=busy || history.length===0; }
function remember() {
  const a=annotations();
  // Rows are immutable strings; only annotation maps need separate copies.
  history.push({...doc,rows:doc.rows.slice(),annotations:{pipes:{...a.pipes},rows:{...a.rows},columns:{...a.columns}}});
  if(history.length>20)history.shift();
  updateUndo();
}
function undo() {
  if(busy || !history.length)return;
  $('menu').hidden=true;
  adopt(history.pop());
  status('Undid the last change.');
}
function tileAt(x,y) {
  if(!doc || x<margin || y<margin)return null;
  const r=Math.floor((y-oy)/cell), c=Math.floor((x-ox)/cell);
  return r>=0 && r<doc.n && c>=0 && c<doc.n-r ? {r,c} : null;
}
function showTileInfo() {
  $('tile-info').hidden=!inspectedTile;
  if(!inspectedTile)return;
  const {r,c}=inspectedTile, cross=doc.rows[r][c]==='1';
  const label=p=>p ? `Pipe ${p}` : 'Outer boundary (no numbered pipe)';
  $('tile-title').textContent=`Tile (${r+1}, ${c+1}) · ${cross ? 'Cross' : 'Elbow'}`;
  $('tile-pipes').textContent=`${tileLabels(r,c)}\n${label(west[r][c])}: ${cross ? 'west → east' : 'west → north'}\n${label(south[r][c])}: ${cross ? 'south → north' : 'south → east'}`;
}
function annotations() {
  const a = doc.annotations || {};
  for (const key of ['pipes', 'rows', 'columns']) {
    if (!a[key] || typeof a[key] !== 'object') a[key] = {};
    for (const id of Object.keys(a[key])) {
      if (!/^#[0-9a-f]{6}$/i.test(a[key][id])) delete a[key][id];
    }
  }
  doc.annotations = a;
  return a;
}
function buildRouting() {
  const below = new Uint16Array(doc.n);
  west = new Array(doc.n); south = new Array(doc.n);
  for (let r = doc.n - 1; r >= 0; r--) {
    west[r] = new Uint16Array(doc.n - r);
    south[r] = new Uint16Array(doc.n - r);
    let left = r + 1;
    for (let c = 0; c < doc.n - r; c++) {
      west[r][c] = left; south[r][c] = below[c];
      if (doc.rows[r][c] === '0') { const next = below[c]; below[c] = left; left = next; }
    }
  }
  topPipes=Array.from(below);
  makeOverview();
}
function makeOverview() {
  overview = document.createElement('canvas'); overview.width = overview.height = doc.n;
  const gc = overview.getContext('2d'), pixels = gc.createImageData(doc.n, doc.n), a = annotations();
  function rgb(hex) { return [1,3,5].map(i => parseInt(hex.slice(i, i+2),16)); }
  const colors = {}; Object.entries(a.pipes).forEach(([k,v]) => colors[k] = rgb(v));
  for (let r = 0; r < doc.n; r++) for (let c = 0; c < doc.n-r; c++) {
    const i = (r*doc.n+c)*4;
    const color = colors[west[r][c]] || colors[south[r][c]] ||
      (doc.rows[r][c] === '1' ? [74,111,101] : [219,231,222]);
    pixels.data.set([...color,255], i);
  }
  gc.putImageData(pixels,0,0);
}
function adopt(next, reset = false) {
  doc = next; annotations(); buildRouting(); $('empty').hidden = true;
  $('n').value = doc.n;
  coordinateMode=selectedCoordinates();
  if(doc.constraint){
    $('pipe').value=doc.constraint.pipe;
    $('turns').value=JSON.stringify(convertTurns(doc.constraint.turns,doc.n,'grid',coordinateMode));
  }
  $('seed').placeholder = doc.seed == null ? 'Random' : `Last: ${doc.seed}`;
  const stats = doc.randomization;
  $('move-summary').textContent = stats ?
    `${stats.applied.toLocaleString()} / ${stats.requested.toLocaleString()} moves · ${stats.ladder.toLocaleString()} ladder + ${(stats.chute || 0).toLocaleString()} chute + ${stats.inverse.toLocaleString()} inverse · ${(stats.non_elementary || 0).toLocaleString()} longer moves${stats.stalled ? ' · No legal moves available.' : ''}${doc.constraint ? ' · Prescribed pipe locked.' : ''}` :
    'Choose 0–100,000 successful moves.';
  const v = doc.validation;
  $('badge').textContent = v.valid ? 'Valid reduced diagram' : 'Edited · invalid for w₀,₂';
  $('badge').className = v.valid ? '' : 'invalid';
  $('counts').textContent = `${doc.n.toLocaleString()} pipes · ${v.crosses.toLocaleString()} crosses`;
  lastInspection=null;$('inspection').textContent='Select a pipe to see its turns.';
  if (reset) { history = []; inspectedTile=null; selected=null; fit(); } else draw();
  $('menu').hidden=true;showTileInfo();updateUndo();
  status(v.valid ? 'Permutation and reducedness verified.' : `Target: ${v.matches_target ? 'yes' : 'no'} · Reduced: ${v.reduced ? 'yes' : 'no'}`);
}
function draw() { if (!frame) frame = requestAnimationFrame(render); }
function render() {
  frame = 0;
  const ratio = window.devicePixelRatio || 1;
  ctx.setTransform(ratio,0,0,ratio,0,0); ctx.clearRect(0,0,width,height);
  if (!doc) return;
  const a = annotations();
  ctx.save(); ctx.beginPath(); ctx.rect(margin,margin,width-margin,height-margin); ctx.clip();
  if (cell < 6) {
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(overview,ox,oy,doc.n*cell,doc.n*cell);
  } else {
    const r0 = Math.max(0,Math.floor((margin-oy)/cell)), r1 = Math.min(doc.n,Math.ceil((height-oy)/cell));
    const c0 = Math.max(0,Math.floor((margin-ox)/cell)), c1 = Math.min(doc.n,Math.ceil((width-ox)/cell));
    for (let r=r0;r<r1;r++) for(let c=c0;c<Math.min(c1,doc.n-r);c++) {
      const x=ox+c*cell,y=oy+r*cell;
      if (a.rows[r+1] || a.columns[c+1]) {
        ctx.globalAlpha=.12; ctx.fillStyle=a.rows[r+1] || a.columns[c+1];ctx.fillRect(x,y,cell,cell);ctx.globalAlpha=1;
      }
      if(cell>=13) {ctx.strokeStyle='#e1e8e2';ctx.lineWidth=.6;ctx.strokeRect(x,y,cell,cell);}
      const cross=doc.rows[r][c]==='1';
      for(let branch=0;branch<2;branch++) {
        const pipe=branch===0?west[r][c]:south[r][c];
        if (!pipe) continue;
        ctx.strokeStyle=a.pipes[pipe] || '#42685d';ctx.lineWidth=Math.max(1,cell*(a.pipes[pipe] ? .085 : .05));
        ctx.beginPath();
        if(cross) {
          if(branch===0){ctx.moveTo(x,y+cell/2);ctx.lineTo(x+cell,y+cell/2);}
          else {ctx.moveTo(x+cell/2,y+cell);ctx.lineTo(x+cell/2,y);}
        } else if(branch===0) ctx.arc(x,y,cell/2,0,Math.PI/2);
        else ctx.arc(x+cell,y+cell,cell/2,Math.PI,Math.PI*1.5);
        ctx.stroke();
      }
    }
  }
  // Row/column color bands remain visible even in the overview.
  ctx.globalAlpha=.22;
  for(const [r,color] of Object.entries(a.rows)){ctx.fillStyle=color;ctx.fillRect(ox,oy+(r-1)*cell,(doc.n-r+1)*cell,Math.max(1,cell*.1));}
  for(const [c,color] of Object.entries(a.columns)){ctx.fillStyle=color;ctx.fillRect(ox+(c-1)*cell,oy,Math.max(1,cell*.1),(doc.n-c+1)*cell);}
  ctx.globalAlpha=1;ctx.restore();
  if(inspectedTile) {
    const {r,c}=inspectedTile;
    ctx.save();ctx.beginPath();ctx.rect(margin,margin,width-margin,height-margin);ctx.clip();
    ctx.strokeStyle='#df6746';ctx.lineWidth=2;ctx.strokeRect(ox+c*cell,oy+r*cell,cell,cell);ctx.restore();
  }
  ctx.fillStyle='#f6f8f4';ctx.fillRect(0,0,width,margin);ctx.fillRect(0,0,margin,height);
  ctx.font='11px Segoe UI';ctx.textAlign='center';ctx.textBaseline='middle';
  const stride=Math.max(1,Math.ceil(30/cell));
  axisBands().forEach((kind,band)=>{
    const center=(band+.5)*bandSize;
    ctx.fillStyle=kind==='pipe'?'#111111':'#1565c0';
    for(let i=0;i<doc.n;i++) if(i%stride===0 || i===doc.n-1){
      const x=ox+(i+.5)*cell,y=oy+(i+.5)*cell;
      if(x>=margin&&x<width)ctx.fillText(axisValue(kind,'x',i)||'–',x,center);
      if(y>=margin&&y<height)ctx.fillText(axisValue(kind,'y',i),center,y);
    }
    ctx.strokeStyle='#dbe3dc';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(0,(band+1)*bandSize);ctx.lineTo(width,(band+1)*bandSize);ctx.moveTo((band+1)*bandSize,0);ctx.lineTo((band+1)*bandSize,height);ctx.stroke();
  });
  $('zoom').textContent=cell<6?'Overview':`${Math.round(cell/28*100)}%`;
}
function fit(){if(!doc)return;width=viewport.clientWidth||width;height=viewport.clientHeight||height;cell=Math.max(.2,Math.min(40,(width-margin-25)/doc.n,(height-margin-25)/doc.n));ox=oy=margin+10;draw();}
function zoom(factor,x=width/2,y=height/2){const next=Math.min(100,Math.max(.2,cell*factor));ox=x-(x-ox)*next/cell;oy=y-(y-oy)*next/cell;cell=next;draw();}
new ResizeObserver(()=>{width=viewport.clientWidth;height=viewport.clientHeight;const dpr=window.devicePixelRatio||1;canvas.width=width*dpr;canvas.height=height*dpr;draw();}).observe(viewport);
canvas.addEventListener('wheel',e=>{e.preventDefault();zoom(Math.exp(-e.deltaY*.002),e.offsetX,e.offsetY);},{passive:false});
canvas.addEventListener('pointerdown',e=>{if(e.button!==0)return;drag={x:e.clientX,y:e.clientY,localX:e.offsetX,localY:e.offsetY,ox,oy,moved:false};canvas.setPointerCapture(e.pointerId);$('menu').hidden=true;});
canvas.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.hypot(dx,dy)>4)drag.moved=true;if(drag.moved){ox=drag.ox+dx;oy=drag.oy+dy;draw();}});
canvas.addEventListener('pointerup',e=>{
  if(drag && !drag.moved && Math.hypot(e.clientX-drag.x,e.clientY-drag.y)<=4){inspectedTile=tileAt(drag.localX,drag.localY);showTileInfo();draw();}
  drag=null;
});
canvas.addEventListener('pointercancel',()=>drag=null);
canvas.addEventListener('contextmenu',e=>{
  e.preventDefault();if(!doc||busy)return;
  const x=e.offsetX,y=e.offsetY,r=Math.floor((y-oy)/cell),c=Math.floor((x-ox)/cell);
  const axis=axisHit(x,y);
  let pipe=0;
  const tile=x>=margin&&y>=margin&&r>=0&&r<doc.n&&c>=0&&c<doc.n-r;
  if(tile){const dx=(x-ox)/cell-c,dy=(y-oy)/cell-r;
    const branch=doc.rows[r][c]==='1' ? (Math.abs(dy-.5)<=Math.abs(dx-.5)?0:1) : (dx+dy<1?0:1);
    pipe=branch===0?west[r][c]:south[r][c];}
  const axisRow=axis?.axis==='y',axisColumn=axis?.axis==='x';
  if(axis?.kind==='pipe')pipe=axis.value;
  if(!tile&&!axisRow&&!axisColumn)return;
  selected={r,c,pipe,tile};
  if(tile){inspectedTile={r,c};showTileInfo();draw();}
  $('location').textContent=tile?`${tileLabels(r,c)}\nSelected pipe ${pipe||'boundary'}`:`${axis.kind==='pipe'?'Black pipe':'Blue edge'} ${axis.value} · ${axisRow?'Y':'X'} axis\n${axisRow?'Row':'Column'} ${axis.index+1}`;
  $('color-pipe').textContent=`Color pipe ${pipe}`;
  $('color-row').textContent=`Color row ${r+1}${axisRow?' ('+(axis.kind==='pipe'?'pipe ':'edge ')+axis.value+')':''}`;
  $('color-column').textContent=`Color column ${c+1}${axisColumn?' ('+(axis.kind==='pipe'?'pipe ':'edge ')+axis.value+')':''}`;
  document.querySelectorAll('#menu button').forEach(b=>{
    b.hidden=(['pipe','inspect'].includes(b.dataset.action)&&!pipe)||(b.dataset.action==='toggle'&&!tile)||
      (b.dataset.action==='row'&&!tile&&!axisRow)||(b.dataset.action==='column'&&!tile&&!axisColumn);
  });
  $('menu').hidden=false;
  $('menu').style.left=`${Math.max(8,Math.min(e.clientX,innerWidth-$('menu').offsetWidth-8))}px`;
  $('menu').style.top=`${Math.max(8,Math.min(e.clientY,innerHeight-$('menu').offsetHeight-8))}px`;
});
document.addEventListener('click',e=>{if(!$('menu').contains(e.target))$('menu').hidden=true;});
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){$('menu').hidden=true;return;}
  const editing=['INPUT','TEXTAREA','SELECT'].includes(e.target?.tagName) || e.target?.isContentEditable;
  if((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==='z' && !e.shiftKey && !e.altKey && !editing){e.preventDefault();undo();}
});
function displayInspection(){
  if(!lastInspection)return;
  const result=lastInspection;
  const black=result.turns.map(([r,c])=>[r,topPipes[c-1]||0]);
  $('inspection').textContent=`Pipe ${result.pipe} → column ${result.exit ?? 'outside'}\n${result.turns.length} turns\nGrid: ${JSON.stringify(result.turns)}\nBlack (Y, X): ${JSON.stringify(black)}\nBlue (Y, X): ${JSON.stringify(convertTurns(result.turns,doc.n,'grid','edge'))}`;
  if(result.turns.length===5){coordinateMode=selectedCoordinates();$('n').value=doc.n;$('turns').value=JSON.stringify(convertTurns(result.turns,doc.n,'grid',coordinateMode));}
}
async function inspect(pipe){if(!doc)throw new Error('Generate a diagram first.');lastInspection=await api('/api/trace',{...doc,pipe});$('pipe').value=pipe;displayInspection();}
$('menu').addEventListener('click',e=>{const action=e.target.dataset.action;if(!action || busy || !selected)return;$('menu').hidden=true;
  if(action==='toggle')return run(async()=>{const next=await api('/api/toggle',{...doc,row:selected.r+1,column:selected.c+1});remember();adopt(next);});
  if(action==='inspect')return run(()=>inspect(selected.pipe));
  const a=annotations(),color=$('color').value;
  const category={pipe:'pipes',row:'rows',column:'columns'}[action];
  const id=action==='pipe'?selected.pipe:action==='row'?selected.r+1:selected.c+1;
  if(!category || !id || a[category][id]===color)return;
  remember();a[category][id]=color;
  makeOverview();draw();
});
function generationInput(){const seed=$('seed').value;const moves=Number($('moves').value);if($('moves').value===''||!Number.isInteger(moves)||moves<0||moves>100000)throw new Error('Enter an integer move count from 0 to 100,000.');return {n:Number($('n').value),seed:seed===''?null:Number(seed),moves,mode:$('mode').value};}
$('generate').onclick=()=>run(async()=>{status('Generating and checking diagram…');adopt(await api('/api/generate',generationInput()),true);});
$('randomize').onclick=()=>run(async()=>{
  if(!doc)throw new Error('Generate a diagram first.');
  const {seed,moves,mode}=generationInput();
  status('Applying random moves…');
  const next=await api('/api/randomize',{...doc,seed,moves,mode});
  if(next.randomization.applied)remember();
  adopt(next);
});
$('constrained').onclick=()=>run(async()=>{
  const input=prescribedInput(), seconds=Number($('seconds').value);
  if(!Number.isFinite(seconds)||seconds<.1||seconds>3600)throw new Error('Enter a search time from 0.1 to 3,600 seconds.');
  input.seconds=seconds;
  const started=Date.now();
  const progress=()=>status(`Finding a completion and applying moves… ${Math.floor((Date.now()-started)/1000)}s elapsed · Search limit ${seconds}s`);
  progress(); $('cancel-search').disabled=false;
  const timer=setInterval(progress,1000);
  try {adopt(await api('/api/generate',input),true);}
  finally {clearInterval(timer);$('cancel-search').disabled=true;}
});
$('cancel-search').onclick=async()=>{
  $('cancel-search').disabled=true;
  try {const result=await api('/api/cancel',{});status(result.cancel_requested?'Cancellation requested…':'Completion search has finished; waiting for random moves.');}
  catch(e){status(e.message,true);}
};
$('inspect').onclick=()=>run(()=>inspect(Number($('pipe').value)));
$('axes').onchange=()=>{const previous=margin;axisView=$('axes').value;margin=bandSize*axisBands().length;ox+=margin-previous;oy+=margin-previous;$('menu').hidden=true;draw();};
$('coordinates').onchange=()=>{
  const next=$('coordinates').value;
  try{if($('turns').value.trim())$('turns').value=JSON.stringify(convertTurns(JSON.parse($('turns').value),Number($('n').value),coordinateMode,next));coordinateMode=next;updateEntranceFromTurns();}
  catch(e){$('coordinates').value=coordinateMode;status(e.message,true);}
};
$('turns').addEventListener('input',updateEntranceFromTurns);
$('n').addEventListener('input',updateEntranceFromTurns);
$('fit').onclick=fit;$('plus').onclick=()=>zoom(1.3);$('minus').onclick=()=>zoom(1/1.3);
$('detail').onclick=()=>{if(!doc)return;cell=28;ox=oy=margin+10;draw();};
$('clear').onclick=()=>{if(doc && !busy && Object.values(annotations()).some(colors=>Object.keys(colors).length)){remember();doc.annotations={};makeOverview();draw();}};
$('undo').onclick=undo;
async function library(){const saved=await api('/api/saved');$('saved').replaceChildren();for(const item of saved){const option=document.createElement('option');option.value=item.id;option.textContent=`${item.name} · N=${item.n}`;$('saved').append(option);}}
$('save').onclick=()=>run(async()=>{if(!doc)throw new Error('Generate a diagram first.');const result=await api('/api/save',{...doc,name:$('name').value});await library();$('saved').value=result.id;status(`Saved diagram #${result.id}.`);});
$('load').onclick=()=>run(async()=>{if(!$('saved').value)throw new Error('No saved diagram selected.');adopt(await api(`/api/saved/${$('saved').value}`),true);});
$('export').onclick=()=>{if(!doc)return;const url=URL.createObjectURL(new Blob([JSON.stringify(doc,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`pipe-dream-${doc.n}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('import').onchange=()=>run(async()=>{const file=$('import').files[0];if(!file)return;if(file.size>4000000)throw new Error('File is too large.');const data=JSON.parse(await file.text());adopt(await api('/api/validate',data),true);$('import').value='';});
run(async()=>{await library();adopt(await api('/api/generate',{n:12,seed:42}),true);});
