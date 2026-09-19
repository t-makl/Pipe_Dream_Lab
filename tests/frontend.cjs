/* Runtime smoke test with a minimal DOM/canvas stand-in, not a visual test.
   Run with Node: node tests/frontend.cjs (while the local server is running). */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');

async function main() {
  const drawContext = new Proxy({createImageData:(w,h)=>({data:new Uint8ClampedArray(w*h*4)})},
    {get:(o,k)=>k in o?o[k]:()=>{}});
  const elements = {};
  const documentEvents = {};
  function element(id) {
    return elements[id] ||= {value:'',style:{},clientWidth:1000,clientHeight:700,offsetWidth:220,offsetHeight:320,events:{},
      addEventListener(name,handler){this.events[name]=handler;},setPointerCapture(){},
      replaceChildren(){},append(){},getContext:()=>drawContext};
  }
  const sandbox = {
    document:{getElementById:element,querySelectorAll:()=>[],addEventListener(name,handler){documentEvents[name]=handler;},createElement:()=>element('offscreen')},
    window:{devicePixelRatio:1},ResizeObserver:class{constructor(cb){this.cb=cb;}observe(){this.cb();}},
    requestAnimationFrame:()=>1,console,Uint16Array,Uint8ClampedArray,setTimeout,setInterval,clearInterval,
    innerWidth:1400,innerHeight:900,
    fetch:(url,options)=>fetch('http://127.0.0.1:8000'+url,options),
  };
  vm.createContext(sandbox);
  let source = fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
  source = source.replace("run(async()=>{await library();adopt(await api('/api/generate',{n:12,seed:42}),true);});",'');
  vm.runInContext(source,sandbox);
  function shortcut(target={tagName:'CANVAS'},overrides={}) {
    let prevented=false;
    documentEvents.keydown({key:'z',ctrlKey:true,target,preventDefault(){prevented=true;},...overrides});
    return prevented;
  }
  function pointer(r,c,dx=0,dy=0) {
    const [x,y]=vm.runInContext(`[ox+(${c}+.25)*cell,oy+(${r}+.5)*cell]`,sandbox);
    const event={button:0,pointerId:1,clientX:x,clientY:y,offsetX:x,offsetY:y};
    element('canvas').events.pointerdown(event);
    if(dx||dy)element('canvas').events.pointermove({...event,clientX:x+dx,clientY:y+dy});
    element('canvas').events.pointerup({...event,clientX:x+dx,clientY:y+dy});
  }
  for (const n of [12,1000]) {
    const response = await fetch('http://127.0.0.1:8000/api/generate',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({n,seed:42})});
    const board = await response.json();
    assert.equal(board.validation.valid,true);
    sandbox.testDocument=board;
    vm.runInContext('adopt(testDocument,true); render(); cell=28; render();',sandbox);
    // Independently walk each JS routing label through the top boundary.
    const exits = vm.runInContext('Array.from({length:doc.n},(_,c)=>doc.rows[0][c]==="1"?south[0][c]:west[0][c])',sandbox);
    assert.deepEqual(Array.from(exits),board.validation.permutation);
    if(n===12) {
      vm.runInContext('cell=28;ox=oy=45;',sandbox);
      let r=board.rows.findIndex(row=>row.includes('1')), c=board.rows[r].indexOf('1');
      pointer(r,c);
      assert.match(element('tile-title').textContent,/Cross/);
      const ids=vm.runInContext(`[west[${r}][${c}],south[${r}][${c}]]`,sandbox);
      for(const id of ids)assert.ok(element('tile-pipes').textContent.includes(`Pipe ${id}:`));
      assert.equal(element('tile-info').hidden,false);
      const previousInfo=element('tile-title').textContent;
      pointer(0,0,30,20);
      assert.equal(element('tile-title').textContent,previousInfo); // Pan is not a click.
      vm.runInContext('ox=oy=45;',sandbox);
      pointer(11,0);
      assert.match(element('tile-pipes').textContent,/Outer boundary/);
      assert.ok(!element('tile-pipes').textContent.includes('Pipe 0'));
      pointer(0,0);
      assert.match(element('tile-title').textContent,/Elbow/);

      const [x,y]=vm.runInContext(`[ox+(${c}+.25)*cell,oy+(${r}+.5)*cell]`,sandbox);
      element('canvas').events.contextmenu({offsetX:x,offsetY:y,clientX:x,clientY:y,preventDefault(){}});
      assert.equal(element('menu').hidden,false);
      element('color').value='#123456';
      element('menu').events.click({target:{dataset:{}}}); // Color picker keeps menu open.
      assert.equal(element('menu').hidden,false);
      element('menu').events.click({target:{dataset:{action:'pipe'}}});
      assert.equal(vm.runInContext(`doc.annotations.pipes[${ids[0]}]`,sandbox),'#123456');
      assert.equal(element('undo').disabled,false);
      assert.equal(shortcut({tagName:'INPUT'}),false); // Native text undo is preserved.
      assert.equal(vm.runInContext('history.length',sandbox),1);
      assert.equal(shortcut(),true);
      assert.equal(vm.runInContext(`doc.annotations.pipes[${ids[0]}]`,sandbox),undefined);
      assert.equal(element('undo').disabled,true);

      for(const action of ['row','column','pipe']) {
        element('menu').events.click({target:{dataset:{action}}});
      }
      element('clear').onclick();
      assert.equal(vm.runInContext('Object.keys(annotations().pipes).length',sandbox),0);
      shortcut(); // Undo clear restores all three colors.
      assert.equal(vm.runInContext(`doc.annotations.rows[${r+1}]`,sandbox),'#123456');
      assert.equal(vm.runInContext(`doc.annotations.columns[${c+1}]`,sandbox),'#123456');
      assert.equal(vm.runInContext(`doc.annotations.pipes[${ids[0]}]`,sandbox),'#123456');
      shortcut();shortcut();shortcut();
      assert.equal(vm.runInContext('history.length',sandbox),0);
      assert.equal(vm.runInContext('Object.keys(annotations().rows).length',sandbox),0);

      await element('menu').events.click({target:{dataset:{action:'toggle'}}});
      assert.equal(vm.runInContext('doc.validation.valid',sandbox),false);
      shortcut(undefined,{ctrlKey:false,metaKey:true});
      assert.equal(vm.runInContext('doc.validation.valid',sandbox),true);
      assert.deepEqual(Array.from(vm.runInContext('doc.rows',sandbox)),board.rows);
      console.log('Tile IDs, click-vs-pan, context color picker, coloring history, Ctrl+Z and Cmd+Z passed.');
    }
    vm.runInContext("annotations().pipes[3]='#df6746';makeOverview();render();",sandbox);
    element('moves').value='7'; element('seed').value='42'; element('mode').value='general';
    await element('randomize').onclick();
    assert.equal(vm.runInContext('doc.randomization.applied',sandbox),7);
    assert.equal(vm.runInContext('doc.randomization.mode',sandbox),'general');
    assert.equal(vm.runInContext('doc.validation.valid',sandbox),true);
    assert.equal(vm.runInContext('doc.annotations.pipes[3]',sandbox),'#df6746');
    assert.match(element('move-summary').textContent,/7 \/ 7 moves/);
    element('undo').onclick();
    assert.deepEqual(Array.from(vm.runInContext('doc.rows',sandbox)),board.rows);
    element('mode').value='elementary';
    await element('randomize').onclick();
    assert.equal(vm.runInContext('doc.randomization.mode',sandbox),'elementary');
    assert.equal(vm.runInContext('doc.randomization.non_elementary',sandbox),0);
    console.log(`Frontend routing / overview / detailed render / colors passed at N=${n}`);
  }
  element('n').value='100';element('pipe').value='39';element('moves').value='0';
  element('turns').value='[[39,19],[19,19],[19,39],[1,39],[1,62]]';
  element('seconds').value='600';element('mode').value='general';
  await element('constrained').onclick();
  assert.equal(vm.runInContext('doc.n',sandbox),100);
  assert.equal(vm.runInContext('doc.validation.valid',sandbox),true);
  assert.equal(vm.runInContext('doc.constraint.pipe',sandbox),39);
  assert.equal(element('cancel-search').disabled,true);
  console.log('Long-budget prescribed search UI passed.');
}
module.exports = main();
if (require.main === module) module.exports.catch(error=>{console.error(error);process.exitCode=1;});
