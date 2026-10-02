import fs from 'node:fs';
import {stream} from '../memory_scope_fix_20261002/.runtime/pi/node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js';
import {createRecorder} from './recorder_v2.mjs';

const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const recorder = createRecorder(input);
const call = recorder.beginCall();
const model = {id: input.model, name: input.model, api: 'openai-completions', provider: 'glm', baseUrl: input.base_url,
  reasoning: true, input: ['text'], contextWindow: 131072, maxTokens: 8192,
  compat: {thinkingFormat: 'zai', supportsReasoningEffort: true, supportsStore: false,
    supportsDeveloperRole: false, maxTokensField: 'max_tokens'}, cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}};
const deadline = new AbortController();
const timer = setTimeout(() => deadline.abort(), 180000);
let final = null;
let failure = null;
try {
  const response = stream(model, {messages: input.messages.map(message => ({...message, timestamp: 0}))},
    {apiKey: process.env.EXPERIMENT_API_KEY, maxTokens: 8192, reasoningEffort: 'high', signal: deadline.signal,
      maxRetries: 2, timeoutMs: 180000,
      fetch: (url, options) => recorder.fetchRecorded(url, options, call),
      onPayload: payload => {
        if (input.response_format) payload.response_format = input.response_format;
        if (Buffer.byteLength(JSON.stringify(payload)) > 320000) throw Error('Registered request byte budget exceeded');
        return payload;
      }});
  for await (const event of response) {
    if (event.type !== 'text_delta' && event.type !== 'thinking_delta') recorder.append('events.jsonl', {event});
    if (event.type === 'done') final = event.message;
    if (event.type === 'error') {final = event.error; failure = event.error.errorMessage ?? event.reason;}
  }
} catch (error) { failure = String(error); }
finally {
  clearTimeout(timer);
  recorder.endCall(call, final?.stopReason ?? 'exception');
  recorder.flush();
  recorder.write('aux-result.json', {message: final, error: failure,
    text: (final?.content ?? []).filter(c => c.type === 'text').map(c => c.text).join('\n')});
}
