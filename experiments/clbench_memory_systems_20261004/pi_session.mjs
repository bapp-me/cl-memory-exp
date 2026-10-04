// Actual Pi coding-agent SDK; no raw agent-core replacement loop.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { createAgentSession, createExtensionRuntime, ModelRuntime, SessionManager, SettingsManager }
  from './.local/node-runtime/node_modules/@earendil-works/pi-coding-agent/dist/index.js';

const root = path.dirname(fileURLToPath(import.meta.url));
const cfg = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = path.resolve(cfg.out);
fs.mkdirSync(path.join(out, 'requests'), {recursive: true});
const append = (file, value) => fs.appendFileSync(path.join(out, file), JSON.stringify(value) + '\n');
const save = (file, value) => fs.writeFileSync(path.join(out, file), JSON.stringify(value, null, 2) + '\n');
const identity = {run_id: cfg.run_id, method_id: cfg.method_id, instance_id: cfg.instance_id,
  project_key: cfg.project_key, agent_id: 'main', parent_agent_id: null, config_hash: cfg.config_hash};
let role = 'solver';
let notepad = cfg.notepad || '';
let terminal = false;
let callCounter = 0;
let outputLimit = 16384;
let lastFinalAssistant = null;
const rawCaptures = [];
const captureErrors = [];
const realFetch = globalThis.fetch;
async function gate(operation, body) {
  if (!cfg.request_gate) return null;
  const response = await realFetch(cfg.request_gate.url + '/' + operation, {method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Gate-Token': cfg.request_gate.token},
    body: JSON.stringify(body)});
  if (!response.ok) throw new Error('Shared request gate failed: ' + response.status);
  return response.json();
}

async function recordedFetch(input, options) {
  const req = new Request(input, options);
  const destination = new URL(req.url);
  if (cfg.fixture ? destination.hostname !== '127.0.0.1' : destination.hostname !== 'api.z.ai') {
    throw new Error('Unexpected provider destination');
  }
  const id = crypto.randomUUID();
  const requestBody = await req.clone().text();
  const payload = JSON.parse(requestBody);
  if (payload.model !== 'glm-5.3-flash') throw new Error('Undeclared model fallback');
  const meta = {...identity, session_id: cfg.session_id, role, call_id: id, attempt_id: id,
    timestamp: new Date().toISOString(), endpoint: req.url};
  const started = performance.now();
  const permit = await gate('acquire', {run_id: cfg.run_id, attempt_id: id, role, session_id: cfg.session_id});
  fs.writeFileSync(path.join(out, 'requests', `${id}.request.json`), requestBody);
  append('attempts.jsonl', {...meta, phase: 'started', gate_wait_seconds: permit?.wait_seconds ?? 0});
  let released = false;
  const release = async () => {
    if (permit && !released) {released = true; await gate('release', {lease: permit.lease});}
  };
  try {
    const response = await realFetch(req);
    const capture = response.clone().text().then(text => {
      // No headers are recorded. Defensive exact-secret removal from server errors.
      const safe = process.env.EXPERIMENT_API_KEY ? text.replaceAll(process.env.EXPERIMENT_API_KEY, '[REDACTED]') : text;
      fs.writeFileSync(path.join(out, 'requests', `${id}.response.txt`), safe);
      append('attempts.jsonl', {...meta, phase: 'finished', status: response.status,
        elapsed_ms: performance.now() - started});
    }).catch(error => {
      append('attempts.jsonl', {...meta, phase: 'capture_failed', error: error.name});
      captureErrors.push({attempt_id: id, error: error.name});
    }).finally(release);
    rawCaptures.push(capture);
    return response;
  } catch (error) {
    await release();
    append('attempts.jsonl', {...meta, phase: 'transport_failed', error: error.name,
      elapsed_ms: performance.now() - started});
    throw error;
  }
}

const agentDir = path.join(out, 'home');
fs.mkdirSync(agentDir, {recursive: true});
const runtime = await ModelRuntime.create({authPath: path.join(agentDir, 'auth.json'),
  modelsPath: null, modelsStorePath: path.join(agentDir, 'models-store.json'), refreshOnCreate: false,
  allowModelNetwork: false});
runtime.registerProvider('glm_experiment', {baseUrl: cfg.base_url, api: 'openai-completions',
  models: [{id: 'glm-5.3-flash', name: 'GLM 5.3 Flash',
    reasoning: true, input: ['text'], contextWindow: 262144, maxTokens: 131072,
    cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}}]});
await runtime.setRuntimeApiKey('glm_experiment', process.env.EXPERIMENT_API_KEY);
// All native summary and solver entry points retain their algorithms, while this
// transport hook captures actual HTTP attempts and disables implicit SDK retries.
for (const name of ['stream', 'streamSimple', 'complete', 'completeSimple']) {
  const original = runtime[name].bind(runtime);
  runtime[name] = (model, context, options = {}) => {
    callCounter++;
    append('contexts.jsonl', {...identity, session_id: cfg.session_id, role,
      sequence: callCounter, model: model.id, contextWindow: model.contextWindow,
      context, timestamp: new Date().toISOString()});
    const maxTokens = role === 'solver' ? outputLimit : Math.min(options.maxTokens ?? 16384, 16384);
    return original(model, context, {...options, fetch: recordedFetch, maxTokens,
      maxRetries: 0, timeoutMs: 300000, transport: 'sse'});
  };
}
const model = runtime.getModel('glm_experiment', 'glm-5.3-flash');
if (!model) throw new Error('Registered GLM model missing');
const settings = SettingsManager.inMemory({compaction: {enabled: true, reserveTokens: 16384, keepRecentTokens: 20000},
  retry: {enabled: false, provider: {maxRetries: 0, timeoutMs: 300000}},
  cacheWarming: 'off', enableAnalytics: false, enableInstallTelemetry: false});
const toolName = 'CLBENCH_ACTION';
const properties = cfg.environment === 'codebase_adaptation'
  ? {command: {type: 'string', description: 'Bash command for the benchmark code workspace.'}}
  : {action: {type: 'string', enum: ['QUERY', 'ANSWER']}, content: {type: 'string'}};
const required = Object.keys(properties);
if (cfg.method_id === 'pi_notepad') properties.notepad_update = {anyOf: [{type: 'string'}, {type: 'null'}],
  description: 'Optional: Update your notepad with new observations, patterns, or thoughts. If provided, this completely replaces the current notepad content. Leave as null to keep notepad unchanged.'};
const tool = {name: toolName, label: 'CL-Bench action', description: cfg.tool_description,
  parameters: {type: 'object', properties, required, additionalProperties: false},
  execute: async (toolCallId, params) => {
    if (terminal) return {content: [{type: 'text', text: 'This instance is already complete. End this turn.'}], details: {}};
    if (cfg.method_id === 'pi_notepad' && params.notepad_update !== undefined && params.notepad_update !== null) {
      if (typeof params.notepad_update !== 'string') throw new Error('Invalid notepad type');
      notepad = params.notepad_update;
    }
    const action = {...params}; delete action.notepad_update;
    const response = await realFetch(cfg.tool_url, {method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-Run-Token': cfg.tool_token},
      body: JSON.stringify({action, notepad, toolCallId})});
    if (!response.ok) throw new Error(`Business tool transport failed: ${response.status}`);
    const result = await response.json();
    terminal = result.instance_complete;
    append('tools.jsonl', {...identity, session_id: cfg.session_id, role: 'solver', toolCallId,
      timestamp: new Date().toISOString(), action, observation: result.observation, notepad,
      instance_complete: terminal});
    save('notepad.json', {value: notepad});
    return {content: [{type: 'text', text: result.observation}], details: {instance_complete: terminal}};
  }};
const resourceLoader = {
  getExtensions: () => ({extensions: [], errors: [], runtime: createExtensionRuntime()}),
  getSkills: () => ({skills: [], diagnostics: []}), getPrompts: () => ({prompts: [], diagnostics: []}),
  getThemes: () => ({themes: [], diagnostics: []}), getAgentsFiles: () => ({agentsFiles: []}),
  getSystemPrompt: () => undefined, getSystemPromptSource: () => undefined,
  getAppendSystemPrompt: () => [cfg.system_append], getAppendSystemPromptSources: () => [],
  extendResources: () => {}, reload: async () => {},
};
const manager = SessionManager.create(cfg.workspace, path.join(out, 'sessions'));
const {session, modelFallbackMessage} = await createAgentSession({cwd: cfg.workspace, agentDir,
  model, modelRuntime: runtime, thinkingLevel: 'high', resourceLoader,
  tools: [toolName], customTools: [tool], settingsManager: settings, sessionManager: manager});
if (modelFallbackMessage) throw new Error('Unexpected model selection fallback');
cfg.session_id = manager.getSessionId();
save('session-start.json', {...identity, session_id: cfg.session_id, model,
  active_tools: session.getActiveToolNames(), system_prompt: session.systemPrompt,
  source_ids: (cfg.sources || []).map(s => s.source_id), sdk: 'pi-coding-agent@1.0.2'});
session.subscribe(event => {
  append('events.jsonl', {...identity, session_id: cfg.session_id, timestamp: new Date().toISOString(), event});
  if (event.type === 'auto_compaction_start') role = 'compaction';
  if (event.type === 'auto_compaction_end') role = 'solver';
  if (event.type === 'message_end' && event.message?.role === 'assistant') lastFinalAssistant = event.message;
});
let timeoutControl = null;
let timedOut = false;
const controlTimer = setInterval(() => {
  const controlFile = path.join(out, 'task-timeout.json');
  if (cfg.fixture && !timeoutControl && fs.existsSync(controlFile)) {
    const control = JSON.parse(fs.readFileSync(controlFile, 'utf8'));
    timedOut = true;
    timeoutControl = (async () => {
      await session.abort();
      await session.sendCustomMessage({customType: 'benchmark-terminal-feedback', display: false,
        content: control.observation, details: {simulated_fixture_cancellation: true}});
      terminal = true;
    })();
  }
}, 100);
try {
  for (const source of cfg.sources || []) {
    const text = JSON.stringify(source.episode);
    for (let offset = 0; offset < text.length; offset += 128000) {
      // Bounded ingestion is solely for the fixed three selected episodes.
      if (JSON.stringify(session.messages).length > 600000) {
        role = 'memory_ingestion_compaction';
        save(`compaction-before-${callCounter}.json`, session.messages);
        await session.compact();
        save(`compaction-after-${callCounter}.json`, session.messages);
        role = 'solver';
      }
      await session.sendCustomMessage({customType: 'legal-history', display: false,
        content: `PAST LEGAL EPISODE ${source.source_id} RANGE ${offset}:${Math.min(offset + 128000, text.length)}\n${text.slice(offset, offset + 128000)}`,
        details: {source_id: source.source_id, offset, length: Math.min(128000, text.length - offset)}});
    }
  }
  if (cfg.force_compact_fixture) {
    role = 'fixture_compaction';
    save('compaction-before-fixture.json', session.messages);
    await session.compact();
    save('compaction-after-fixture.json', session.messages);
    role = 'solver';
  }
  const prefix = [];
  if (cfg.method_id === 'pi_notepad' && cfg.previous_feedback) prefix.push('FEEDBACK FROM PREVIOUS INSTANCE:\n' + cfg.previous_feedback);
  if (cfg.method_id === 'pi_notepad' && notepad) prefix.push('=== YOUR NOTEPAD ===\n' + notepad + '\n===================');
  prefix.push(cfg.prompt);
  await session.prompt(prefix.join('\n\n'), {expandPromptTemplates: false});
  while (!terminal && !timedOut) {
    // Pi can remove a truncated assistant from projected context during native
    // recovery. Use its authoritative completion event, retained in the audit.
    const last = lastFinalAssistant;
    if (last?.stopReason !== 'length' || outputLimit >= 131072) break;
    const previous = outputLimit;
    outputLimit = Math.min(outputLimit * 2, 131072);
    // User authorized automatic output expansion. All methods retain the 256k
    // window and reserve enough room before their next request; no silent overflow.
    settings.applyOverrides({compaction: {enabled: true, reserveTokens: outputLimit, keepRecentTokens: 20000}});
    append('output-budget-adjustments.jsonl', {...identity, session_id: cfg.session_id,
      timestamp: new Date().toISOString(), from: previous, to: outputLimit,
      effective_compaction_trigger: 262144 - outputLimit, cause: 'provider_finish_reason_length',
      retained_same_instance_and_session: true});
    lastFinalAssistant = null;
    await session.prompt('Continue the same benchmark instance using its existing observations. Finish the next business action; do not restart completed work.',
      {expandPromptTemplates: false});
  }
  if (timeoutControl) await timeoutControl;
  await session.waitForIdle();
  await Promise.all(rawCaptures);
  if (captureErrors.length && !timedOut) throw new Error('Incomplete provider response capture');
  save('session-end.json', {...identity, session_id: cfg.session_id, terminal, notepad,
    messages: session.messages, entries: manager.getEntries(), provider_entry_calls: callCounter,
    pending_message_count: session.pendingMessageCount, timed_out: timedOut, capture_errors: captureErrors,
    final_output_limit: outputLimit});
  if (!terminal) throw new Error('Agent ended before a benchmark submission');
  process.stdout.write(JSON.stringify({ok: true, session_id: cfg.session_id, terminal}) + '\n');
} finally {
  clearInterval(controlTimer);
  await session.waitForIdle();
  session.dispose();
  await Promise.all(rawCaptures);
}
