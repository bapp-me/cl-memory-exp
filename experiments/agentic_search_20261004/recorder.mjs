import {performance} from 'node:perf_hooks';
import {createRecorder as baseRecorder, hash} from '../section7_observability_20261002/recorder_v2.mjs';

// Passive extension: map dynamic tool results into actual provider requests.
export function createRecorder(input) {
  const base = baseRecorder(input);
  const registered = new Map();
  function registerMemory(id, result, serialized) {
    if (registered.has(id)) throw Error('Duplicate memory tool call ID');
    const item = {tool_call_id: id, result_sha256: hash(serialized), serialized,
      library_hash: result.library_hash,
      ranges: (result.items ?? []).map(({content, ...range}) => ({...range, excerpt_sha256: hash(content)}))};
    registered.set(id, item);
    base.append('memory-results.jsonl', item);
  }
  async function fetchRecorded(url, options, call) {
    const raw = typeof options.body === 'string' ? options.body : Buffer.from(options.body ?? '').toString();
    const payload = JSON.parse(raw);
    const mappings = [];
    for (const item of registered.values()) {
      const matches = [];
      for (const [index, message] of (payload.messages ?? []).entries()) {
        const content = typeof message.content === 'string' ? message.content :
          (message.content ?? []).filter(c => c.type === 'text').map(c => c.text).join('');
        if (message.role === 'tool' && message.tool_call_id === item.tool_call_id) {
          if (content !== item.serialized) throw Error('Memory tool result changed before actual request');
          matches.push({message_index: index, role: message.role, utf8_bytes: Buffer.byteLength(content),
            char_unit: 'javascript_utf16', char_start: 0, char_end: content.length});
        }
      }
      mappings.push({tool_call_id: item.tool_call_id, result_sha256: item.result_sha256,
        ranges: item.ranges, matches, status: matches.length ? 'visible' : 'absent_from_this_payload'});
    }
    const attempt = call.http_attempts.length + 1;
    base.append('memory-exposure.jsonl', {call_id: call.call_id, http_attempt: attempt,
      actual_body_sha256: hash(raw), mappings, active_result_count: mappings.filter(m => m.matches.length).length,
      token_count: null, token_measurement_method: 'no_tokenizer_attribution'});
    const started = performance.now();
    const response = await base.fetchRecorded(url, options, call);
    if (!response.body) return response;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let firstByte = null, firstText = null, firstTool = null, bytes = 0, chunks = 0, pending = '', finished = false;
    const finish = reason => {
      if (finished) return;
      finished = true;
      base.append('stream-timing.jsonl', {call_id: call.call_id, http_attempt: attempt,
        first_observed_body_ms: firstByte, first_visible_text_ms: firstText, first_tool_delta_ms: firstTool,
        observed_bytes: bytes, chunks, duration_ms: performance.now() - started, reason});
    };
    const body = new ReadableStream({
      async pull(controller) {
        try {
          const {done, value} = await reader.read();
          if (done) { finish('eof'); controller.close(); return; }
          const elapsed = performance.now() - started;
          firstByte ??= elapsed; bytes += value.byteLength; chunks++;
          pending += decoder.decode(value, {stream: true});
          const lines = pending.split('\n'); pending = lines.pop();
          for (const line of lines) {
            if (!line.startsWith('data:')) continue;
            try {
              const data = JSON.parse(line.slice(5));
              for (const choice of data.choices ?? []) {
                if (choice.delta?.content) firstText ??= elapsed;
                if (choice.delta?.tool_calls?.length) firstTool ??= elapsed;
              }
            } catch { /* SSE control frames are not JSON. */ }
          }
          controller.enqueue(value);
        } catch (error) { finish(String(error)); controller.error(error); }
      },
      async cancel(reason) { finish('consumer_cancelled'); await reader.cancel(reason); }
    });
    return new Response(body, {status: response.status, statusText: response.statusText, headers: response.headers});
  }
  return {...base, registerMemory, fetchRecorded};
}
