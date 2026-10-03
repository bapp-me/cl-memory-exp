// Native completion/apply/store functions; scripted completion, no network.
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const root=path.dirname(fileURLToPath(import.meta.url));
const home=fs.mkdtempSync(path.join(root,'.runtime','component-'));
process.env.PI_CODING_AGENT_DIR=home;
globalThis.fetch=async()=>{throw Error('No network allowed in component fixture');};
net.Socket.prototype.connect=function(){throw Error('No network allowed in component fixture');};
const {MemoryStore}=await import('./.runtime/node_modules/pi-hermes-memory/src/store/memory-store.ts');
const {loadConfig}=await import('./.runtime/node_modules/pi-hermes-memory/src/config.ts');
const {runDirectMemoryCompletion,applyReviewOperations}=await import('./.runtime/node_modules/pi-hermes-memory/src/handlers/review-memory-ops.ts');
const config=loadConfig(path.join(home,'absent-config.json'));
const model={provider:'fixture',id:'fixture-model',api:'openai-completions',baseUrl:'http://127.0.0.1:1/v1',reasoning:false,input:['text'],contextWindow:131072,maxTokens:4096,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
const ctx:any={model,modelRegistry:{getAll:()=>[model],getApiKeyAndHeaders:async()=>({ok:true,apiKey:'fixture-not-a-secret'}),hasConfiguredAuth:()=>true,isUsingOAuth:()=>false},sessionManager:{getSessionId:()=> 'component-fixture'}};
const rows:any[]=[];
async function makeStore(name:string) {
  const memoryDir=path.join(home,name);
  const store=new MemoryStore({...config,memoryDir,autoConsolidate:false});
  await store.loadFromDisk();
  return {store,file:path.join(memoryDir,'MEMORY.md')};
}
const read=(file:string)=>fs.existsSync(file)?fs.readFileSync(file,'utf8'):'';
const add={action:'add',target:'memory',content:'Fixture reusable knowledge uses cobalt totals.'};
const replaceMissing={action:'replace',target:'memory',old_text:'Fixture nonexistent old entry',content:'Fixture replacement knowledge.'};
for(const [name,operations,expected] of [['valid',[add],1],['missing_replace',[replaceMissing],0],['partial',[add,replaceMissing],1]] as const) {
  const {store,file}=await makeStore(name);
  const response:any={role:'assistant',content:[{type:'text',text:JSON.stringify({operations})}],stopReason:'stop',usage:{input:101,output:13,totalTokens:114,cacheRead:0,cacheWrite:0},timestamp:0};
  const result=await runDirectMemoryCompletion(ctx,store,null,{userPrompt:'Synthetic operations',systemPrompt:'Synthetic fixture',config,timeoutMs:1000},null,null,{completeSimple:async()=>response});
  assert.equal(result.ok,true);assert.equal(result.appliedCount,expected);
  assert(!('usage' in result));assert(!('skippedCount' in result));
  const comparison=await makeStore(name+'-apply');
  const applyResult=await applyReviewOperations(comparison.store,null,operations as any);
  assert.equal(applyResult.skippedCount,operations.length-expected);
  rows.push({case:name,proposed_count:operations.length,completion_usage:response.usage,direct_result:result,apply_result:applyResult,memory:read(file)});
}
const {store,file}=await makeStore('observer');
let release:()=>void=()=>{},entered:()=>void=()=>{},finished=false;
const gate=new Promise<void>(resolve=>{release=resolve;});
const observerEntered=new Promise<void>(resolve=>{entered=resolve;});
store.setMutationObserver(async()=>{entered();await gate;return 'Synthetic mirror unavailable';});
const operation=store.add('memory','Fixture durable file with delayed mirror.').then(result=>{finished=true;return result;});
await observerEntered;
const during={memory:read(file),write_promise_resolved:finished};
assert(during.memory.includes('delayed mirror'));assert.equal(finished,false);
release();const observed=await operation;
assert.equal(observed.success,true);assert(observed.warnings?.includes('Synthetic mirror unavailable'));
rows.push({case:'observer_barrier_and_warning',during_observer:during,write_result:observed,note:'Injected observer models a delayed/unavailable mirror; this is not a real SQLite failure injection.'});
const result={passed:true,model_calls:0,paid_http_requests:0,component_cases:rows.length,synthetic_usage_only:true,home,rows,
  fixture_script_sha256:createHash('sha256').update(fs.readFileSync(fileURLToPath(import.meta.url))).digest('hex')};
fs.mkdirSync(path.join(root,'records','component'),{recursive:true});
fs.writeFileSync(path.join(root,'records','component','result.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result));
