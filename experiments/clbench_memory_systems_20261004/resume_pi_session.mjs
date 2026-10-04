// Transport-only continuation using the existing native coding-agent session.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {AgentSession, SessionManager}
  from './.local/node-runtime/node_modules/@earendil-works/pi-coding-agent/dist/index.js';

const cfg=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const expected=JSON.parse(fs.readFileSync(cfg.failed_request_file,'utf8'));
const fetchBefore=globalThis.fetch;
let first=true;
globalThis.fetch=async (input, options)=>{
  const request=new Request(input,options);
  if (new URL(request.url).hostname==='api.z.ai' && first) {
    first=false;
    const actual=JSON.parse(await request.clone().text());
    assert.deepEqual(actual,expected,'Transport retry changed the provider request');
    fs.writeFileSync(cfg.retry_verification_file,JSON.stringify({wire_identical:true,model_calls:cfg.resume_dry_run?0:null}));
    if (cfg.resume_dry_run) throw new Error('OFFLINE_IDENTICAL_REQUEST_VERIFIED');
  }
  return fetchBefore(request);
};
SessionManager.create=()=>SessionManager.open(cfg.resume_session_file);
const originalPrompt=AgentSession.prototype.prompt;
let firstPrompt=true;
AgentSession.prototype.prompt=async function(text,options) {
  if (!firstPrompt) return originalPrompt.call(this,text,options);
  firstPrompt=false;
  // Keep the native Session wrapper, post-run hooks, persistence and compaction.
  // Empty input resumes the existing transcript without another user prompt.
  return this._runAgentPrompt([]);
};
await import('./pi_session.mjs');
