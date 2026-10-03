import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import crypto from 'node:crypto';
import {stream} from '../memory_scope_fix_20261002/.runtime/pi/node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js';
import {createRecorder} from './recorder.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));
let requests = 0;
const server = http.createServer(async (req, res) => {
  for await (const chunk of req) { /* consume the request without retaining credentials */ }
  requests++;
  if (requests === 1) {
    res.writeHead(503, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({error: {message: 'fixture transient failure', type: 'server_error'}}));
    return;
  }
  res.writeHead(200, {'Content-Type': 'text/event-stream'});
  res.write('data: ' + JSON.stringify({id: 'fixture', model: 'glm-5.3-flash',
    choices: [{index: 0, delta: {role: 'assistant', content: 'done'}, finish_reason: null}]}) + '\n\n');
  res.write('data: ' + JSON.stringify({choices: [{index: 0, delta: {}, finish_reason: 'stop'}]}) + '\n\n');
  // Intentionally omit usage: a successful HTTP response does not prove known billing.
  res.end('data: [DONE]\n\n');
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const out = path.join(root, '.runtime/recorder-fixtures', crypto.randomUUID());
const recorder = createRecorder({out, run_id: 'fixture', task_id: 'failure', attempt_id: 'fixture', memory_blocks: []});
const historical = {memory_version: 'fixture', library_hash: 'fixture-source', items: []};
recorder.registerMemory('fixture_memory', historical, JSON.stringify(historical));
const model = {id: 'glm-5.3-flash', name: 'glm-5.3-flash', api: 'openai-completions', provider: 'glm',
  baseUrl: `http://127.0.0.1:${server.address().port}/v1`, reasoning: true, input: ['text'],
  contextWindow: 131072, maxTokens: 8192,
  compat: {thinkingFormat: 'zai', supportsReasoningEffort: true, supportsStore: false,
    supportsDeveloperRole: false, maxTokensField: 'max_tokens'},
  cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}};
const call = recorder.beginCall();
try {
  const result = stream(model, {systemPrompt: 'Fixture only.', messages: [{role: 'user', content: 'test', timestamp: 0}]},
    {apiKey: 'fixture-not-secret', maxRetries: 2, fetch: (url, init) => recorder.fetchRecorded(url, init, call)});
  for await (const event of result) { /* SDK consumes and retries */ }
  recorder.endCall(call, 'done'); recorder.flush();
  assert.equal(requests, 2);
  assert.equal(call.http_attempts.length, 2);
  assert.equal(call.http_attempts[0].status, 503);
  assert.equal(call.http_attempts[1].status, 200);
  assert(call.http_attempts.every(attempt => attempt.raw_usage === null));
  const exposures = fs.readFileSync(path.join(out, 'memory-exposure.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
  assert.equal(exposures.length, 2);
  assert(exposures.every(row => row.mappings[0].status === 'absent_from_this_payload'));
  assert(fs.readFileSync(path.join(out, 'stream-timing.jsonl'), 'utf8').includes('first_visible_text_ms'));
  const logFiles = fs.readdirSync(out).filter(name => name.endsWith('.json') || name.endsWith('.jsonl'));
  assert(logFiles.every(name => !fs.readFileSync(path.join(out, name), 'utf8').includes('fixture-not-secret')));
  console.log(JSON.stringify({passed: true, paid_model_calls: 0, mock_requests: requests,
    checks: ['503 retry shares generation ID', 'failed and successful missing usage stays unknown',
      'absent historical result not claimed visible', 'stream timing', 'credentials excluded']}));
} finally { await new Promise(resolve => server.close(resolve)); }
