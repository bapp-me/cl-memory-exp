import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import crypto from 'node:crypto';
import {stream} from '../memory_scope_fix_20261002/.runtime/pi/node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js';
import {createRecorder, sanitize} from './recorder.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));
const capture = [];
let recordedAttempts = 0;
const server = http.createServer(async (req, res) => {
  let body = '';
  for await (const chunk of req) body += chunk;
  capture.push({url: req.url, payload: JSON.parse(body)});
  if (req.url.startsWith('/recorded') && ++recordedAttempts === 1) {
    res.writeHead(503, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({error: {message: 'fixture retry', type: 'server_error'}}));
    return;
  }
  res.writeHead(200, {'Content-Type': 'text/event-stream'});
  res.write('data: ' + JSON.stringify({id: 'fixture-response', model: 'glm-5.3-flash',
    choices: [{index: 0, delta: {role: 'assistant', content: 'fixture complete'}, finish_reason: null}]}) + '\n\n');
  res.write('data: ' + JSON.stringify({choices: [{index: 0, delta: {}, finish_reason: 'stop'}]}) + '\n\n');
  if (!req.url.startsWith('/unknown')) res.write('data: ' + JSON.stringify({choices: [],
    usage: {prompt_tokens: 100, completion_tokens: 7, prompt_tokens_details: {cached_tokens: 20}, total_tokens: 107}}) + '\n\n');
  res.end('data: [DONE]\n\n');
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const episode = JSON.stringify({sequence: 0, text: 'legal episode'});
const context = {messages: [{role: 'system', content: 'Same legacy system\n[' + episode + ']', timestamp: 0},
  {role: 'user', content: 'fixture prompt', timestamp: 0}]};
const model = {id: 'glm-5.3-flash', name: 'glm-5.3-flash', api: 'openai-completions', provider: 'glm',
  reasoning: true, input: ['text'], contextWindow: 131072, maxTokens: 8192,
  compat: {thinkingFormat: 'zai', supportsReasoningEffort: true, supportsStore: false,
    supportsDeveloperRole: false, maxTokensField: 'max_tokens'}, cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}};
const fixtureKey = crypto.randomUUID();
const input = suffix => ({out: path.join(root, '.runtime/fixtures/recorder', fixtureKey, suffix), run_id: 'fixture',
  task_id: suffix, attempt_id: 'fixture.' + suffix, memory_blocks: [{memory_id: 'legal-episode-id', serialized: episode}]});
const collect = async response => { const events = []; for await (const event of response) events.push(event); return events; };
try {
  await collect(stream({...model, baseUrl: base + '/baseline'}, context,
    {apiKey: 'fixture-key', maxTokens: 8192, reasoningEffort: 'high', maxRetries: 2}));
  const recorder = createRecorder(input('recorded'));
  const call = recorder.beginCall();
  const observed = await collect(stream({...model, baseUrl: base + '/recorded'}, context,
    {apiKey: 'fixture-key', maxTokens: 8192, reasoningEffort: 'high', maxRetries: 2,
      fetch: (url, options) => recorder.fetchRecorded(url, options, call)}));
  recorder.endCall(call, 'stop'); recorder.flush();
  assert.deepEqual(capture[0].payload, capture[1].payload);
  assert.deepEqual(capture[1].payload, capture[2].payload);
  assert.equal(call.http_attempts.length, 2);
  assert.equal(call.http_attempts[0].status, 503);
  assert.equal(call.http_attempts[0].raw_usage, null);
  assert.equal(call.http_attempts[1].raw_usage.total_tokens, 107);
  assert.equal(call.http_attempts[1].sse_done_received, true);
  assert.equal(call.http_attempts[1].error, undefined);
  assert.equal(observed.at(-1).type, 'done');
  const requests = fs.readFileSync(path.join(input('recorded').out, 'requests.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
  assert(requests.every(r => r.all_injected_blocks_mapped));
  assert(!JSON.stringify(JSON.parse(fs.readFileSync(path.join(input('recorded').out, 'call-ledger.json')))).includes('fixture-key'));
  const unknown = createRecorder(input('unknown'));
  const unknownCall = unknown.beginCall();
  await collect(stream({...model, baseUrl: base + '/unknown'}, context,
    {apiKey: 'fixture-key', fetch: (url, options) => unknown.fetchRecorded(url, options, unknownCall)}));
  unknown.endCall(unknownCall, 'stop'); unknown.flush();
  assert.equal(unknownCall.http_attempts[0].raw_usage, null);
  assert.equal(sanitize({Authorization: 'secret', nested: {api_key: 'secret'}}).nested.api_key, '[REDACTED]');
  console.log(JSON.stringify({model_calls: 0, mock_requests: capture.length, passed: true,
    checks: ['SDK request payload unchanged', '503 retry shares call ID', 'failed usage remains unknown',
             'complete stream end recorded', 'actual injection spans mapped', 'no credential artifacts', 'missing usage remains null']}));
} finally { await new Promise(resolve => server.close(resolve)); }
