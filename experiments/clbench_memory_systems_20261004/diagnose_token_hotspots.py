"""Read-only stage attribution of native provider usage in a bounded window."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
from prepare import ROOT, read, save
from summarize_results import response_usage, normalize


def stage_for(request, after_submission):
    metadata = request.get('client_metadata') or {}
    native_role = metadata.get('x-openai-subagent')
    if native_role == 'memory_consolidation':
        return 'codex_native_memory_consolidation'
    if (request.get('text') or {}).get('format', {}).get('type') == 'json_schema':
        return 'codex_native_memory_extraction'
    return 'post_submission_other' if after_submission else 'pre_submission_solver_and_auxiliary'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--end', required=True, help='UTC ISO timestamp; requests are assigned by start time')
    parser.add_argument('--minutes', type=int, default=30)
    parser.add_argument('--output', required=True, help='Public JSON report under records/')
    args = parser.parse_args()
    end = datetime.fromisoformat(args.end)
    if end.tzinfo is None:
        raise ValueError('Timezone required')
    start = end - timedelta(minutes=args.minutes)
    groups = defaultdict(list)
    tools = defaultdict(Counter)
    for path in (ROOT / 'private-runs').glob('*/task-*/requests/*.attempt.json'):
        meta = read(path)
        stamp = datetime.fromisoformat(meta['timestamp'])
        if not start <= stamp <= end:
            continue
        ident = meta['attempt_id']
        request_path = path.with_name(ident + '.native-request.json')
        if not request_path.exists():
            request_path = path.with_name(ident + '.request.json')
        request = read(request_path)
        submission = path.parent.parent / 'submission.json'
        after = submission.exists() and stamp.timestamp() >= submission.stat().st_mtime
        stage = stage_for(request, after)
        usage, _, finish, _ = response_usage(path.with_name(ident + '.response.bin'))
        normalized = normalize(usage, meta['protocol'])
        row = {'attempt_id': ident, 'task': path.parent.parent.name,
               'phase': meta.get('phase'), 'error': meta.get('error'),
               'http_status': meta.get('http_status'), 'finish_reason': finish, **normalized}
        key = (meta['run_id'], stage)
        groups[key].append(row)
        # Only tool names, never arguments or business content, enter the public report.
        raw = path.with_name(ident + '.response.bin')
        if raw.exists() and stage == 'codex_native_memory_consolidation':
            for line in raw.read_text(encoding='utf8').splitlines():
                if not line.startswith('data: '):
                    continue
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if event.get('type') == 'response.output_item.done':
                    item = event.get('item', {})
                    if item.get('type') in {'function_call', 'custom_tool_call'}:
                        tools[key][item.get('name', 'unknown')] += 1
    fields = ['input_tokens', 'cached_input_tokens', 'output_tokens', 'total_tokens']
    rows = []
    for (run, stage), attempts in groups.items():
        rows.append({'run_id': run, 'stage': stage, 'attempts': len(attempts),
                     'unknown_usage': sum(x['total_tokens'] is None for x in attempts),
                     'in_flight': sum(x['phase'] == 'started' for x in attempts),
                     'error_attempts': sum(bool(x['error']) or (x['http_status'] or 0) >= 400 for x in attempts),
                     'max_output': max((x['output_tokens'] or 0) for x in attempts),
                     **{field: sum(x[field] or 0 for x in attempts) for field in fields},
                     'tool_names': dict(tools[(run, stage)]), 'attempt_evidence': attempts})
    rows.sort(key=lambda row: row['total_tokens'], reverse=True)
    report = {'as_of': datetime.now(timezone.utc).isoformat(), 'window_start': start.isoformat(),
              'window_end': end.isoformat(), 'minutes': args.minutes,
              'scope': 'Native experiment provider requests started in this interval; excludes Codex desktop chat usage',
              'attribution': 'Codex consolidation uses native x-openai-subagent metadata; extraction uses native JSON schema. Other stages use submission timestamp and include native auxiliary calls.',
              'limits': ['Usage observed at report time; in-flight and failed unknown usage are not zero.',
                         'Cached input is included within input; token volume is not actual billed cost.',
                         'Tool names count completed Responses tool items, not token attribution by individual tool.'],
              'totals': {field: sum(row[field] for row in rows) for field in fields}, 'rows': rows}
    target = (ROOT / args.output).resolve()
    if not target.is_relative_to((ROOT / 'records').resolve()):
        raise ValueError('Output must be under records/')
    save(target, report)
    print(json.dumps({**{k: v for k, v in report.items() if k != 'rows'},
                      'rows': [{k: v for k, v in r.items() if k != 'attempt_evidence'} for r in rows]}))


if __name__ == '__main__':
    main()
