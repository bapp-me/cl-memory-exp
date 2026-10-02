import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { performance } from 'node:perf_hooks';

export const hash = value => crypto.createHash('sha256').update(value).digest('hex');
export const sanitize = value => {
  if (Array.isArray(value)) return value.map(sanitize);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, val]) =>
    [key, /^(authorization|api[_-]?key|access[_-]?token|tool_token|broker_token)$/i.test(key) ? '[REDACTED]' : sanitize(val)]));
  return value;
};

export function createRecorder(input) {
  fs.mkdirSync(input.out, { recursive: true });
  const identity = {schema_version: 'section7-observability-v1', run_id: input.run_id,
    task_id: input.task_id, attempt_id: input.attempt_id, role: 'solver'};
  const append = (name, value) => fs.appendFileSync(path.join(input.out, name), JSON.stringify({...identity,
    at: new Date().toISOString(), monotonic_ms: performance.now(), ...sanitize(value)}) + '\n');
  const write = (name, value) => {
    const target = path.join(input.out, name);
    fs.mkdirSync(path.dirname(target), {recursive: true});
    fs.writeFileSync(target, JSON.stringify(sanitize(value), null, 2) + '\n');
  };
  const calls = [];
  let call = null;
  let ordinal = 0;
  const beginCall = () => {
    call = {...identity, call_id: `${input.attempt_id}.call-${++ordinal}`, started_at: new Date().toISOString(),
      started_monotonic_ms: performance.now(), finished_at: null, duration_monotonic_ms: null, http_attempts: []};
    calls.push(call);
    append('calls.jsonl', {...call, event: 'generation_start'});
    return call;
  };
  const endCall = (current, status) => {
    if (!current || current.finished_at) return;
    current.finished_at = new Date().toISOString();
    current.duration_monotonic_ms = performance.now() - current.started_monotonic_ms;
    current.status = status;
    append('calls.jsonl', {...current, event: 'generation_end'});
  };
  const spans = payload => {
    const blocks = input.memory_blocks ?? [];
    const mapped = blocks.map(block => {
      const matches = [];
      for (const [messageIndex, message] of (payload.messages ?? []).entries()) {
        const text = typeof message.content === 'string' ? message.content :
          (message.content ?? []).filter(c => c.type === 'text').map(c => c.text).join('');
        const start = text.indexOf(block.serialized);
        if (start >= 0) matches.push({message_index: messageIndex, role: message.role,
          char_start: start, char_end: start + block.serialized.length,
          utf8_bytes: Buffer.byteLength(block.serialized), token_count: null, token_measurement_method: 'unavailable'});
      }
      return {memory_id: block.memory_id, content_sha256: hash(block.serialized), matches};
    });
    return {blocks: mapped, all_injected_blocks_mapped: mapped.every(b => b.matches.some(m => m.role === 'system' || m.role === 'developer'))};
  };
  const savePayload = (payload, current, attempt, raw) => {
    const artifact = `payloads/${current.call_id}.http-${attempt}.json`;
    write(artifact, payload);
    const mapping = spans(payload);
    append('requests.jsonl', {call_id: current.call_id, http_attempt: attempt, artifact,
      actual_body_sha256: hash(raw), sanitized_payload_sha256: hash(JSON.stringify(sanitize(payload))),
      bytes: Buffer.byteLength(raw), model: payload.model, ...mapping});
    if (!mapping.all_injected_blocks_mapped) throw Error('Injected memory block missing from actual system payload');
  };
  const fetchRecorded = async (url, options, current = call) => {
    if (!current) throw Error('Generation must have an identity before HTTP');
    const attempt = current.http_attempts.length + 1;
    const entry = {call_id: current.call_id, http_attempt: attempt, started_at: new Date().toISOString(),
      started_monotonic_ms: performance.now(), status: null, finished_at: null, raw_usage: null,
      provider_model: null, provider_response_id: null, monetary_cost: null, usage_provenance: 'not_returned'};
    current.http_attempts.push(entry);
    const raw = typeof options.body === 'string' ? options.body : Buffer.from(options.body ?? '').toString();
    append('transport.jsonl', {...entry, event: 'http_start'});
    const finish = error => {
      if (entry.finished_at) return;
      entry.finished_at = new Date().toISOString();
      entry.duration_monotonic_ms = performance.now() - entry.started_monotonic_ms;
      if (error) entry.error = String(error);
      append('transport.jsonl', {...entry, event: 'http_end'});
    };
    try {
      savePayload(JSON.parse(raw), current, attempt, raw);
      const response = await fetch(url, options);
      entry.status = response.status;
      entry.headers_seconds = (performance.now() - entry.started_monotonic_ms) / 1000;
      append('transport.jsonl', {...entry, event: 'http_headers'});
      if (!response.body) { finish(); return response; }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let pending = '';
      const inspect = text => {
        pending += text;
        const lines = pending.split('\n');
        pending = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          if (line.slice(5).trim() === '[DONE]') { entry.sse_done_received = true; continue; }
          try {
            const data = JSON.parse(line.slice(5).trim());
            entry.provider_model = data.model ?? entry.provider_model;
            entry.provider_response_id = data.id ?? entry.provider_response_id;
            entry.provider_finish_reasons = [...new Set([...(entry.provider_finish_reasons ?? []),
              ...(data.choices ?? []).map(c => c.finish_reason).filter(Boolean)])];
            const usage = data.usage ?? data.choices?.find(c => c.usage)?.usage;
            if (usage) { entry.raw_usage = usage; entry.usage_provenance = 'provider_sse'; }
          } catch { /* SSE includes [DONE] and optional non-JSON frames. */ }
        }
      };
      const body = new ReadableStream({
        async pull(controller) {
          try {
            const {value, done} = await reader.read();
            if (done) { inspect(decoder.decode() + '\n'); finish(); controller.close(); }
            else { inspect(decoder.decode(value, {stream: true})); controller.enqueue(value); }
          } catch (error) { finish(error); controller.error(error); }
        },
        async cancel(reason) {
          entry.completion_reason = entry.sse_done_received ? 'sdk_closed_after_sse_done' : 'consumer_cancelled_without_done';
          finish(entry.sse_done_received ? undefined : reason ?? 'consumer_cancelled');
          await reader.cancel(reason);
        }
      });
      return new Response(body, {status: response.status, statusText: response.statusText, headers: response.headers});
    } catch (error) { finish(error); throw error; }
  };
  const flush = () => {
    for (const current of calls) {
      endCall(current, current.status ?? 'terminated');
      for (const attempt of current.http_attempts) if (!attempt.finished_at) {
        attempt.finished_at = new Date().toISOString();
        attempt.duration_monotonic_ms = performance.now() - attempt.started_monotonic_ms;
        attempt.error = 'consumer_terminated_before_full_stream';
        append('transport.jsonl', {...attempt, event: 'http_end'});
      }
    }
    write('call-ledger.json', calls);
  };
  return {append, write, calls, beginCall, endCall, fetchRecorded, flush};
}
