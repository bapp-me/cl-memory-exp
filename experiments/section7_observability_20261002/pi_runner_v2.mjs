import fs from 'node:fs';
import { Agent } from '../memory_scope_fix_20261002/.runtime/pi/node_modules/@earendil-works/pi-agent-core/dist/index.js';
import { stream } from '../memory_scope_fix_20261002/.runtime/pi/node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js';
import {createRecorder} from './recorder_v2.mjs';

const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const recorder = createRecorder(input);
let submitted = false, toolCalls = 0, turns = 0, contextExceeded = false;
let responseTimedOut = false, responseTimer = null, currentCall = null;
const tools = input.tools.map(s => ({...s, label: s.name, execute: async (id, args) => {
  if (submitted) return {content: [{type: 'text', text: 'Already submitted.'}], terminate: true};
  toolCalls++;
  recorder.append('tools.jsonl', {event: 'tool_start', tool_call_id: id, call_id: currentCall?.call_id, name: s.name, args});
  const response = await fetch(input.tool_url, {method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Run-Token': input.tool_token},
    body: JSON.stringify({name: s.name, args, tool_call_id: id})});
  if (!response.ok) throw Error(`Tool HTTP ${response.status}`);
  const result = await response.json();
  submitted = !!result.submitted;
  recorder.append('tools.jsonl', {event: 'tool_end', tool_call_id: id, call_id: currentCall?.call_id,
    name: s.name, result, submitted});
  return {content: [{type: 'text', text: JSON.stringify(result)}], isError: !!result.error,
    ...(submitted ? {terminate: true} : {})};
}}));
const model = {id: input.model, name: input.model, api: 'openai-completions', provider: input.provider,
  baseUrl: input.base_url, reasoning: true, input: ['text'], contextWindow: 131072, maxTokens: 8192,
  compat: {thinkingFormat: 'zai', supportsReasoningEffort: true, supportsStore: false,
    supportsDeveloperRole: false, maxTokensField: 'max_tokens'},
  cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}};
const agent = new Agent({initialState: {systemPrompt: input.system, model, tools, thinkingLevel: 'high'},
  toolExecution: 'sequential', streamFn: (m, context, options) => {
    const deadline = new AbortController();
    currentCall = recorder.beginCall();
    const ownCall = currentCall;
    responseTimer = setTimeout(() => {responseTimedOut = true; deadline.abort();}, input.response_timeout_ms);
    return stream(m, context, {...options, signal: AbortSignal.any([options.signal, deadline.signal].filter(Boolean)),
      apiKey: process.env.EXPERIMENT_API_KEY, maxTokens: 8192, reasoningEffort: 'high',
      maxRetries: 2, timeoutMs: input.response_timeout_ms,
      fetch: (url, init) => recorder.fetchRecorded(url, init, ownCall),
      onPayload: payload => {
        if (Buffer.byteLength(JSON.stringify(payload), 'utf8') > 320000) {
          contextExceeded = true; throw Error('Registered request byte budget exceeded');
        }
        return payload;
      }});
  }, finishTurn: async () => (++turns >= input.max_turns || submitted ? {action: 'end'} : undefined)});
agent.subscribe(event => {
  if (event.type === 'message_end' && event.message.role === 'assistant') {
    clearTimeout(responseTimer);
    recorder.endCall(currentCall, event.message.stopReason ?? 'message_end');
  }
  if (event.type !== 'message_update') recorder.append('events.jsonl', {event_type: event.type,
    call_id: currentCall?.call_id ?? null, event});
});
const timer = setTimeout(() => agent.abort(), input.timeout_seconds * 1000);
let error = null;
try { await agent.prompt(input.prompt); } catch (failure) { error = String(failure); }
finally {
  clearTimeout(timer); clearTimeout(responseTimer); recorder.flush();
  const messages = agent.state.messages;
  const final = messages.filter(m => m.role === 'assistant').at(-1);
  recorder.write('pi-result.json', {messages, turns, toolCalls, submitted, contextExceeded, responseTimedOut,
    error: error ?? agent.state.errorMessage ?? null, stop_reason: final?.stopReason ?? null,
    final_response: (final?.content ?? []).filter(c => c.type === 'text').map(c => c.text).join('\n')});
}
