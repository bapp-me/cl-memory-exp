// Real Pi SDK + published plugin, deterministic loopback completions. No paid model.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import net from 'node:net';
import { fileURLToPath, pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

const root = path.dirname(fileURLToPath(import.meta.url));
const scenario = process.argv[2] ?? 'single';
const home = fs.mkdtempSync(path.join(root, '.runtime', `${scenario}-`));
const work = path.join(home, 'work');
fs.mkdirSync(work);
fs.writeFileSync(path.join(work, 'package.json'), '{"name":"synthetic-fixture","private":true}');
for (const key of Object.keys(process.env)) {
  if (/API_KEY|API_TOKEN|AUTH_TOKEN/i.test(key)) delete process.env[key];
}
process.env.PI_CODING_AGENT_DIR = home;
const config = ['flush_one','flush_parse_fail','fallback_success'].includes(scenario) ? {flushMinTurns: 1}
  : scenario==='consolidate' ? {memoryMode:'legacy-inject',memoryCharLimit:220,overflowGraceMs:0}
  : scenario==='overflow_grace' ? {memoryMode:'legacy-inject',memoryCharLimit:220} : {};
fs.writeFileSync(path.join(home, 'hermes-memory-config.json'), JSON.stringify(config));
const out = path.join(root, 'records', scenario);
fs.mkdirSync(out, {recursive: true});
const requests = [], events = [], checkpoints = [], sessions = [];
const event = (kind, data={}) => events.push({index: events.length, kind, monotonic_ms: performance.now(), ...data});
let phase = '', holdReview = ['review_hold', 'review_abort'].includes(scenario);
let releaseReview;
const gate = new Promise(resolve => { releaseReview = resolve; });
const pending = new Set();
const memoryPath = path.join(home, 'pi-hermes-memory', 'MEMORY.md');
const memory = () => fs.existsSync(memoryPath) ? fs.readFileSync(memoryPath, 'utf8') : '';
const snapshot = label => {
  const value = {label, memory: memory(), memory_sha256: createHash('sha256').update(memory()).digest('hex'),
    pending_requests: [...pending], requests: requests.length, monotonic_ms: performance.now()};
  checkpoints.push(value); return value;
};
const textOf = m => typeof m?.content === 'string' ? m.content : (m?.content ?? []).map(x=>x.text??'').join('\n');
function classify(body) {
  const content = body.messages.map(textOf).join('\n');
  if (content.includes('--- User Correction to Save ---')) return 'correction';
  if (content.includes('--- Conversation to Review ---')) return 'review';
  if (content.includes('--- Current Memory ---') && content.includes('--- Conversation ---')) return 'flush';
  return 'solver';
}
function respond(res, row, {text='Fixture finished.', tool, args}={}) {
  if (res.destroyed) return;
  row.status = 'completed'; row.synthetic_usage = {prompt_tokens: 101, completion_tokens: 13, total_tokens: 114};
  res.writeHead(200, {'content-type':'text/event-stream'});
  const chunk=(delta, finish_reason=null)=>({id:`fixture-${row.id}`,object:'chat.completion.chunk',created:0,model:'fixture-model',choices:[{index:0,delta,finish_reason}]});
  const delta = tool ? {role:'assistant',tool_calls:[{index:0,id:`tool-${row.id}`,type:'function',function:{name:tool,arguments:JSON.stringify(args)}}]} : {role:'assistant',content:text};
  res.end([chunk(delta),chunk({},tool?'tool_calls':'stop'),{id:`fixture-${row.id}`,object:'chat.completion.chunk',created:0,model:'fixture-model',choices:[],usage:row.synthetic_usage}]
    .map(c=>`data: ${JSON.stringify(c)}\n\n`).join('')+'data: [DONE]\n\n');
  row.ended_ms=performance.now(); pending.delete(row.id); event('http_complete',{call_id:row.id,role:row.role});
}
const server = http.createServer(async (req,res)=>{
  let raw=''; for await (const chunk of req) raw+=chunk;
  let body; try {body=JSON.parse(raw);} catch {res.writeHead(400).end();return;}
  const child=String(req.headers['x-fixture-pid'])!==String(process.pid);
  const childSolver=child && Array.isArray(body.tools)&&body.tools.length>0;
  const role=child ? (childSolver ? 'child_'+(scenario==='consolidate'?'consolidate_solver':'fallback_solver') : 'child_'+classify(body)) : classify(body);
  const row={id:requests.length+1,phase,role,pid:req.headers['x-fixture-pid'],status:'pending',started_ms:performance.now(),synthetic_usage:null,body};
  requests.push(row); pending.add(row.id); event('http_start',{call_id:row.id,role:row.role});
  res.on('close',()=>{if(row.status==='pending'){row.status='aborted';row.ended_ms=performance.now();pending.delete(row.id);event('http_aborted',{call_id:row.id,role:row.role});}});
  if(childSolver){
    const lastUserIndex=body.messages.findLastIndex(m=>m.role==='user');
    const results=body.messages.slice(lastUserIndex+1).filter(m=>m.role==='tool');
    if(results.length===0) return respond(res,row, scenario==='consolidate'
      ? {tool:'memory_replace',args:{target:'memory',old_text:'Fixture old verbose',content:'Fixture compacted cobalt.'}}
      : {tool:'memory_add',args:{target:'memory',content:'Fixture child flush knowledge uses cobalt totals.'}});
    return respond(res,row,{text:'Saved fixture child memory.'});
  }
  if (row.role!=='solver') {
    if(row.role==='review' && holdReview) await gate;
    if(!child&&['flush_parse_fail','fallback_success'].includes(scenario)) return respond(res,row,{text:'synthetic invalid operation payload'});
    respond(res,row,{text:JSON.stringify({operations:[{action:'add',target:'memory',content:`Fixture ${row.role} knowledge uses cobalt totals.`}]})});
    return;
  }
  const lastUser=body.messages.findLast(m=>m.role==='user');
  const lastUserIndex=body.messages.lastIndexOf(lastUser);
  const tail=body.messages.slice(lastUserIndex+1);
  const toolResults=tail.filter(m=>m.role==='tool');
  const prompt=textOf(lastUser);
  if(prompt.includes('WRITE_FIXTURE') && toolResults.length===0) return respond(res,row,{tool:'memory_add',args:{target:'memory',content:'Fixture foreground knowledge uses cobalt totals.'}});
  if(prompt.includes('READ_FIXTURE') && toolResults.length===0) return respond(res,row,{tool:'memory_search',args:{query:'cobalt'}});
  if(prompt.includes('CONSOLIDATE_FIXTURE') && toolResults.length===0) return respond(res,row,{tool:'memory_add',args:{target:'memory',content:'Fixture additional knowledge about cobalt totals and all current schema constraints.'}});
  const match=prompt.match(/PROBE_(\d+)/);
  if(match && toolResults.length<Number(match[1])) return respond(res,row,{tool:'PROBE',args:{step:toolResults.length}});
  respond(res,row);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const port=server.address().port, endpoint=`http://127.0.0.1:${port}/v1`;
process.env.FIXTURE_PORT=String(port);
process.env.FIXTURE_PROCESS_LOG=path.join(out,'processes.jsonl');
fs.writeFileSync(process.env.FIXTURE_PROCESS_LOG,'');
const guard=pathToFileURL(path.join(root,'fixture_guard.mjs')).href;
process.env.NODE_OPTIONS=`--import=${guard}`;
await import(guard);
const originalConnect=net.Socket.prototype.connect;
const deniedConnections=[];
net.Socket.prototype.connect=function(...args){
  const options=Array.isArray(args[0])?args[0][0]:args[0];
  const host=typeof options==='object'?options.host:args[1];
  const destinationPort=typeof options==='object'?options.port:options;
  if(host!=='127.0.0.1' || Number(destinationPort)!==port) {
    deniedConnections.push({host:String(host),port:String(destinationPort)});
    throw Error('Fixture network allowlist: own loopback endpoint only');
  }
  return originalConnect.apply(this,args);
};
const pkg=(name,relative='dist/index.js')=>pathToFileURL(path.join(root,'.runtime/node_modules',name,relative)).href;
let outcome={scenario,passed:false};
try {
  const {createAgentSession,DefaultResourceLoader,ModelRuntime,SessionManager,SettingsManager}=await import(pkg('@earendil-works/pi-coding-agent'));
  const settings=()=>SettingsManager.inMemory({compaction:{enabled:false},retry:{enabled:false},packages:[],extensions:[]});
  const runtime=await ModelRuntime.create({authPath:path.join(home,'auth.json'),modelsPath:null,refreshOnCreate:false,allowModelNetwork:false});
  runtime.registerProvider('fixture',{baseUrl:endpoint,api:'openai-completions',apiKey:'fixture-no-secret',models:[{id:'fixture-model',name:'Fixture',reasoning:false,input:['text'],contextWindow:131072,maxTokens:2048,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}}]});
  const model=runtime.getModel('fixture','fixture-model'); assert(model);
  if(['fallback_success','consolidate'].includes(scenario)) {
    fs.writeFileSync(path.join(home,'models.json'),JSON.stringify({providers:{fixture:{baseUrl:endpoint,api:'openai-completions',apiKey:'fixture-no-secret',models:[{id:'fixture-model',name:'Fixture',reasoning:false,input:['text'],contextWindow:131072,maxTokens:2048,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}}]}}}));
  }
  if(['consolidate','overflow_grace'].includes(scenario)) {
    fs.mkdirSync(path.dirname(memoryPath),{recursive:true});fs.writeFileSync(memoryPath,'Fixture old verbose knowledge about cobalt totals. '+'Earlier schema details. '.repeat(3));
  }
  const plugin=path.join(root,'.runtime/node_modules/pi-hermes-memory/src/index.ts');
  async function start(label) {
    phase=label;
    const s=settings();
    const loader=new DefaultResourceLoader({cwd:work,agentDir:home,settingsManager:s,noExtensions:true,noSkills:true,noPromptTemplates:true,noThemes:true,noContextFiles:true,
      additionalExtensionPaths:[plugin],systemPrompt:'Synthetic lifecycle fixture. Use only the provided tools.'});
    await loader.reload();
    assert.equal(loader.getExtensions().errors.length,0,JSON.stringify(loader.getExtensions().errors));
    assert.equal(loader.getExtensions().extensions.length,1);
    const {session}=await createAgentSession({cwd:work,agentDir:home,modelRuntime:runtime,model,thinkingLevel:'off',settingsManager:s,resourceLoader:loader,
      sessionManager:SessionManager.create(work,path.join(home,'sessions')),noTools:'builtin',
      customTools:[{name:'PROBE',label:'Probe',description:'Return a synthetic observation.',parameters:{type:'object',properties:{step:{type:'integer'}},required:['step']},
        execute:async(_id,args)=>({content:[{type:'text',text:`Fixture observation ${args.step}`}],details:{}})}]});
    session.subscribe(e=>{ if(e.type!=='message_update') event('session_event',{session:label,event_type:e.type,
      role:e.message?.role,usage:e.message?.usage??null,tool:e.toolName??null}); });
    await session.bindExtensions({onError:e=>event('extension_error',{session:label,error:String(e.error??e)})});
    sessions.push(session); event('session_bound',{session:label,tools:session.getActiveToolNames()});
    return session;
  }
  async function close(session,kind='shutdown') {
    event('close_start',{kind});
    if(kind==='shutdown') await session.extensionRunner.emit({type:'session_shutdown',reason:'exit'});
    session.dispose();event('close_end',{kind});
  }
  async function prompt(session,text) {await session.prompt(text);await session.waitForIdle();event('prompt_idle',{phase});}
  if(scenario==='single') {
    for(let i=0;i<12;i++){const s=await start(`independent-${i}`);await prompt(s,'Calculate the synthetic observation.');await close(s);}
    assert.equal(requests.filter(r=>r.role!=='solver').length,0);assert.equal(memory(),'');
  } else if(scenario==='many_tools') {
    const s=await start('one-user-many-tools');await prompt(s,'PROBE_20');await close(s);
    assert.equal(requests.filter(r=>r.role==='solver').length,21);assert.equal(requests.filter(r=>r.role!=='solver').length,0);
  } else if(scenario==='foreground') {
    const a=await start('write');await prompt(a,'WRITE_FIXTURE');snapshot('after_foreground_write');await close(a);
    assert(memory().includes('foreground knowledge'));
    const b=await start('read');await prompt(b,'READ_FIXTURE');
    assert(b.messages.some(m=>m.role==='toolResult'&&JSON.stringify(m).includes('cobalt')));await close(b);
  } else if(['dispose_six','shutdown_six','flush_one','flush_parse_fail','fallback_success'].includes(scenario)) {
    const s=await start(scenario);for(let i=0;i<(['flush_one','flush_parse_fail','fallback_success'].includes(scenario)?1:6);i++)await prompt(s,`Synthetic task ${i}.`);
    snapshot('before_close');await close(s,scenario==='dispose_six'?'dispose':'shutdown');snapshot('after_close');
    const expected=scenario==='dispose_six'?0:1;assert.equal(requests.filter(r=>r.role==='flush').length,expected);
    assert.equal(memory().includes('flush knowledge'),expected===1&&scenario!=='flush_parse_fail');
    if(scenario==='fallback_success') assert.equal(requests.filter(r=>r.role==='child_fallback_solver').length,2);
  } else if(['consolidate','overflow_grace'].includes(scenario)) {
    const s=await start(scenario);snapshot('before_overflow');await prompt(s,'CONSOLIDATE_FIXTURE');snapshot('after_overflow');await close(s);
    if(scenario==='consolidate') {assert(memory().includes('compacted cobalt'));assert(memory().includes('additional knowledge'));assert.equal(requests.filter(r=>r.role==='child_consolidate_solver').length,2);}
    else {assert(!memory().includes('additional knowledge'));assert.equal(requests.length,2);assert(JSON.stringify(requests.at(-1).body).includes('deferred for 180000ms'));}
  } else if(['review_hold','review_abort'].includes(scenario)) {
    const s=await start(scenario);await prompt(s,'Synthetic first task.');await prompt(s,'Synthetic second task.');await prompt(s,'PROBE_9');
    for(let i=0;i<100&&!requests.some(r=>r.role==='review');i++)await new Promise(r=>setTimeout(r,10));
    const before=snapshot('prompt_and_waitForIdle_resolved');assert.equal(requests.filter(r=>r.role==='review').length,1);assert(pending.size>0);assert.equal(memory(),'');
    if(scenario==='review_hold') {
      releaseReview();for(let i=0;i<200&&!memory().includes('review knowledge');i++)await new Promise(r=>setTimeout(r,10));
      assert(memory().includes('review knowledge'));snapshot('review_committed_after_release');await close(s);
    } else {
      await close(s);releaseReview();await new Promise(r=>setTimeout(r,50));snapshot('after_shutdown');assert.equal(memory(),'');
      assert(requests.some(r=>r.role==='review'&&r.status==='aborted'));
    }
  } else if(scenario==='correction') {
    const s=await start('correction');await prompt(s,'No, use cobalt totals instead.');snapshot('prompt_returned');await close(s);
    assert.equal(requests.filter(r=>r.role==='correction').length,1);assert(memory().includes('correction knowledge'));
  } else throw Error('Unknown scenario');
  assert.equal(deniedConnections.length,0,JSON.stringify(deniedConnections));
  assert.equal(events.filter(e=>e.kind==='extension_error').length,0,JSON.stringify(events.filter(e=>e.kind==='extension_error')));
  outcome={...outcome,passed:true};
} catch(error) {outcome.error=String(error.stack??error);process.exitCode=1;}
finally {
  releaseReview();for(const s of sessions){try{s.dispose();}catch{}}
  server.closeAllConnections();await new Promise(r=>server.close(r));net.Socket.prototype.connect=originalConnect;
  const roles=Object.fromEntries([...new Set(requests.map(r=>r.role))].map(role=>[role,requests.filter(r=>r.role===role).length]));
  const sessionAssistant=events.filter(e=>e.kind==='session_event'&&e.event_type==='message_end'&&e.role==='assistant');
  outcome={...outcome,model_calls:0,paid_http_requests:0,loopback_fixture_requests:requests.length,roles,
    synthetic_usage_only:true,session_assistant_messages:sessionAssistant.length,session_assistant_total_tokens:sessionAssistant.reduce((s,e)=>s+(e.usage?.totalTokens??0),0),
    transport_known_synthetic_tokens:requests.reduce((s,r)=>s+(r.synthetic_usage?.total_tokens??0),0),
    transport_unknown_usage_requests:requests.filter(r=>!r.synthetic_usage).length,
    denied_connections:deniedConnections,config_overrides:config,checkpoints,memory_final:memory(),home,
    fixture_script_sha256:createHash('sha256').update(fs.readFileSync(fileURLToPath(import.meta.url))).digest('hex'),
    subprocess_network_guard:'NODE_OPTIONS inherited; own loopback only',
    note:'Synthetic usage and scripted answers are protocol fixtures, not model performance evidence'};
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(outcome,null,2)+'\n');
  fs.writeFileSync(path.join(out,'events.jsonl'),events.map(e=>JSON.stringify(e)).join('\n')+'\n');
  fs.writeFileSync(path.join(out,'requests.json'),JSON.stringify(requests,null,2)+'\n');
  console.log(JSON.stringify({...outcome,checkpoints:checkpoints.map(c=>({label:c.label,pending_requests:c.pending_requests})),memory_final:outcome.memory_final.slice(0,180)}));
}
