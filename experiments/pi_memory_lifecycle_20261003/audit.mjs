// Offline verification of the final fixture set, dependency identities and evidence hashes.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const read=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const hash=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const norm=p=>fs.readFileSync(p,'utf8').replace(/\r\n/g,'\n');
const cases=['single','many_tools','foreground','dispose_six','shutdown_six','flush_one','correction','review_hold','review_abort','flush_parse_fail','fallback_success','consolidate','overflow_grace'];
const rows=[];
const evidence=[];
const check=(p)=>evidence.push({path:p,sha256:hash(path.join(root,p)),bytes:fs.statSync(path.join(root,p)).size});
for(const name of cases){
  const result=read(`records/${name}/result.json`),requests=read(`records/${name}/requests.json`);
  assert(result.passed);assert.equal(result.model_calls,0);assert.equal(result.paid_http_requests,0);
  assert.equal(result.fixture_script_sha256,hash(path.join(root,'sdk_fixture.mjs')));
  assert.equal(requests.length,result.loopback_fixture_requests);
  assert(requests.every(r=>['completed','aborted'].includes(r.status)));
  assert.equal(requests.filter(r=>!r.synthetic_usage).length,result.transport_unknown_usage_requests);
  assert.equal(requests.reduce((n,r)=>n+(r.synthetic_usage?.total_tokens??0),0),result.transport_known_synthetic_tokens);
  const processLog=fs.readFileSync(path.join(root,`records/${name}/processes.jsonl`),'utf8').trim().split('\n').map(JSON.parse);
  assert(!processLog.some(e=>e.kind==='network_denied'));
  for(const start of processLog.filter(e=>e.kind==='process_start'))assert(processLog.some(e=>e.kind==='process_exit'&&e.pid===start.pid),`Unsettled process ${start.pid}`);
  rows.push({scenario:name,passed:true,roles:result.roles,loopback_requests:requests.length,main_session_synthetic_tokens:result.session_assistant_total_tokens,all_known_synthetic_tokens:result.transport_known_synthetic_tokens,unknown_usage_requests:result.transport_unknown_usage_requests,config:result.config_overrides,memory_nonempty:!!result.memory_final,processes_started:processLog.filter(e=>e.kind==='process_start').length});
  for(const f of ['result.json','requests.json','events.jsonl','processes.jsonl'])check(`records/${name}/${f}`);
}
const component=read('records/component/result.json');assert(component.passed);assert.equal(component.component_cases,4);
assert.equal(component.fixture_script_sha256,hash(path.join(root,'component_fixture.mts')));check('records/component/result.json');
const lock=read('runtime-package-lock.json');
assert.equal(hash(path.join(root,'runtime-package-lock.json')),hash(path.join(root,'.runtime/package-lock.json')));
const packages=['@earendil-works/pi-coding-agent','@earendil-works/pi-agent-core','@earendil-works/pi-ai','pi-hermes-memory','better-sqlite3','tsx'].map(name=>{
  const entry=lock.packages[`node_modules/${name}`],installed=read(`.runtime/node_modules/${name}/package.json`);
  assert.equal(entry.version,installed.version);return {name,version:entry.version,integrity:entry.integrity};
});
const pluginFiles=['src/index.ts','src/config.ts','src/constants.ts','src/handlers/background-review.ts','src/handlers/session-flush.ts','src/handlers/review-memory-ops.ts','src/handlers/correction-detector.ts','src/handlers/auto-consolidate.ts','src/handlers/pi-child-process.ts','src/handlers/child-process-watchdog.mjs','src/store/memory-store.ts','src/tools/memory-tool.ts'];
const sources=pluginFiles.map(p=>{
  const installed=path.join(root,'.runtime/node_modules/pi-hermes-memory',p),cached=path.join(root,'../memory_ecosystem_20261003/.cache/pi-hermes-memory',p);
  assert.equal(norm(installed),norm(cached),`Text changed: ${p}`);
  return {path:p,installed_sha256:hash(installed),upstream_cache_sha256:hash(cached),equal_after_crlf_normalization:true,url:`https://github.com/chandra447/pi-hermes-memory/blob/c93e2885e57e79ae907cf3d718f9633d066b0217/${p}`};
});
for(const p of ['dist/core/agent-session.js','dist/core/extensions/runner.js','dist/core/sdk.js'])sources.push({package:'@earendil-works/pi-coding-agent@1.0.0',path:p,installed_sha256:hash(path.join(root,'.runtime/node_modules/@earendil-works/pi-coding-agent',p)),url:`https://unpkg.com/@earendil-works/pi-coding-agent@1.0.0/${p}`});
fs.writeFileSync(path.join(root,'records/source-map.json'),JSON.stringify({plugin_npm_version:'0.9.10',plugin_npm_gitHead:'df624056a2e8c68bc89ba0a81e1c120856ec9665',upstream_reference_sha:'c93e2885e57e79ae907cf3d718f9633d066b0217',comparison:'Only listed source files; CRLF normalized. No claim of whole repository identity.',packages,sources},null,2)+'\n');
for(const p of ['sdk_fixture.mjs','component_fixture.mts','fixture_guard.mjs','runtime-package.json','runtime-package-lock.json','records/source-map.json'])check(p);
const output={schema:'pi-memory-lifecycle-audit-v1',date:'2026-10-03',timezone:'Asia/Hong_Kong',passed:true,sdk_scenarios:rows.length,component_cases:component.component_cases,
  model_calls:0,paid_model_requests:0,final_set_loopback_requests:rows.reduce((n,r)=>n+r.loopback_requests,0),final_set_known_synthetic_tokens:rows.reduce((n,r)=>n+r.all_known_synthetic_tokens,0),final_set_unknown_usage_requests:rows.reduce((n,r)=>n+r.unknown_usage_requests,0),
  native_source_edits:0,production_adapter_implemented:false,online_compatibility_verified:false,s0_accepted:false,
  scope:'Final deterministic fixture set only; excludes earlier fixture debugging/replays. Token values are scripted, not performance/cost measurements.',rows,evidence};
fs.writeFileSync(path.join(root,'records/completion-audit.json'),JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify({...output,rows:undefined,evidence:undefined}));
