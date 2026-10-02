// Pure payload construction from saved messages; onPayload aborts before HTTP.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {stream} from '../memory_scope_fix_20261002/.runtime/pi/node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js';
const root = path.dirname(fileURLToPath(import.meta.url));
const legacy = path.join(root, '../agent_memory_plan_20261002/runs');
const names = ['full-codeeval-glm-no_memory', 'full-codeeval-glm-episodic_retrieval',
  'noncode-babyai-glm-no_memory', 'noncode-babyai-glm-episodic_retrieval'];
const model = {id: 'glm-5.3-flash', name: 'glm-5.3-flash', api: 'openai-completions', provider: 'glm',
  baseUrl: 'https://api.z.ai/api/paas/v4', reasoning: true, input: ['text'], contextWindow: 131072, maxTokens: 8192,
  compat: {thinkingFormat: 'zai', supportsReasoningEffort: true, supportsStore: false,
    supportsDeveloperRole: false, maxTokensField: 'max_tokens'}, cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}};
const checks = [];
let requestCount = 0;
let accidentalFetch = 0;
for (const name of names) {
  for (const folder of fs.readdirSync(path.join(legacy, name)).filter(name => /^\d+$/.test(name)).sort()) {
    const dir = path.join(legacy, name, folder);
    const result = JSON.parse(fs.readFileSync(path.join(dir, 'pi-result.json'), 'utf8'));
    const expected = fs.readFileSync(path.join(dir, 'requests.jsonl'), 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
    const sizes = [];
    for (let i = 0; i < result.messages.length; i++) {
      if (result.messages[i].role !== 'assistant') continue;
      let bytes = null;
      const response = stream(model, {messages: result.messages.slice(0, i)}, {apiKey: 'offline-not-a-real-key',
        maxTokens: 8192, reasoningEffort: 'high', maxRetries: 0,
        onPayload: payload => {bytes = Buffer.byteLength(JSON.stringify(payload)); throw Error('OFFLINE_CAPTURE_COMPLETE');},
        fetch: async () => {accidentalFetch++; throw Error('Offline audit forbids HTTP');}});
      for await (const event of response) { /* Consume local construction failure only. */ }
      if (bytes !== null) sizes.push(bytes);
    }
    requestCount += sizes.length;
    checks.push({run_id: name, task_directory: folder, expected_payloads: expected.length,
      reconstructed_payloads: sizes.length, all_byte_counts_match: sizes.length === expected.length && sizes.every((size, i) => size === expected[i].bytes),
      expected_sizes: expected.map(r => r.bytes), reconstructed_sizes: sizes});
  }
}
const report = {language_model_calls: 0, http_calls: accidentalFetch, tasks: checks.length, reconstructed_payloads: requestCount,
  byte_checks_passed: accidentalFetch === 0 && checks.every(c => c.all_byte_counts_match), checks,
  limits: ['Old exact payload hash was not recorded; size/source equality supports reconstruction but is not an old cryptographic body comparison.',
    'Mutable model aliases and different historical concurrency remain limitations; old latency cannot be used as a uniform speed comparison.']};
fs.writeFileSync(path.join(root, 'records/legacy-payload-reconstruction.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({tasks: report.tasks, reconstructed_payloads: requestCount, language_model_calls: 0,
  http_calls: accidentalFetch, byte_checks_passed: report.byte_checks_passed,
  mismatch_tasks: checks.filter(c => !c.all_byte_counts_match).map(c => ({run_id: c.run_id, task: c.task_directory, expected: c.expected_sizes, got: c.reconstructed_sizes}))}));
