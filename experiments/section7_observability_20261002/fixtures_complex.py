"""Certify the real adapters with fixed native replies and local embeddings only."""
import json
from pathlib import Path
import uuid
from runtime import ROOT, read, save, digest
from complex_memory import make_adapter


def config():
    common = read(ROOT / 'records/confirmed-config-v1.json')
    native = read(ROOT / 'records/complex-confirmed-config-v1.json')
    return {**common, 'config_id': 'section7-complex-effective-v1', 'native_method_config': native,
            'stream_tasks': 8, 'status': 'fixture'}


def main():
    current = config()
    episode = {'sequence': 0, 'text': json.dumps({'task': 'Use declared tools to inspect and finish a navigation goal.',
               'trajectory': [{'type': 'toolCall', 'name': 'ACTION', 'arguments': {'action': 'check available actions'}},
                              {'tool': 'ACTION', 'content': [{'type': 'text', 'text': 'Available actions: move forward, turn left'}]}]})}
    cases = [
        ('awm', ['## Workflow inspect_then_act\nGoal: navigate safely\n1. Check available actions.\n2. Execute an available action.']),
        ('ace', ['{"reflection":"Use only visible feedback","bullet_tags":[]}',
                 '{"reasoning":"Visible observation supports this routine","operations":[{"type":"ADD","section":"STRATEGIES & INSIGHTS","content":"Check available actions before moving.","reason":"Visible tool observation"}]}']),
        ('mem0', ['{"facts":["Navigation tasks expose available actions through the ACTION tool."]}',
                  '{"memory":[{"id":"0","text":"Navigation tasks expose available actions through the ACTION tool.","event":"ADD"}]}'])]
    checks = []
    for method, replies in cases:
        run_id = 'fixture-' + method + '-' + uuid.uuid4().hex
        folder = ROOT / '.runtime/fixtures/complex' / run_id
        folder.mkdir(parents=True)
        adapter = make_adapter(method, run_id, current, 'fixture-key', fixture_responses=replies)
        try:
            identity = {'run_id': run_id, 'task_id': 'fixture', 'attempt_id': run_id + '.attempt-1', 'method': method, 'benchmark': 'babyai'}
            adapter.task(folder, identity)
            before = adapter.snapshot()
            empty, selection = adapter.retrieve('inspect navigation actions')
            assert empty == [], (method, empty)
            after = adapter.update(episode)
            selected, retrieval = adapter.retrieve('inspect navigation actions')
            assert selected and retrieval['injected_ids'], (method, after)
            assert adapter.state['episode_count'] == 1
            assert after['provenance'], (method, after)
            snapshot = adapter.snapshot()
            adapter.restore(snapshot)
            assert digest(adapter.snapshot()) == digest(snapshot), method
            calls = list(folder.glob('auxiliary/*/fixture-result.json'))
            assert len(calls) == (1 if method == 'awm' else 2), method
            assert all(read(path)['model_calls'] == 0 for path in calls)
            changes = read(folder / 'native-operations.json')
            assert changes['operations'] and changes['source_event_ids'] == [identity['attempt_id']]
            checks.append({'method': method, 'passed': True, 'native_mutation': changes['operations'],
                           'fixture_generation_responses': len(calls), 'language_model_api_calls': 0,
                           'snapshot_restore_hash_equal': True, 'candidate_to_injection_ids': retrieval['injected_ids']})
        finally:
            adapter.close()
    # Native ACE implementation must not be silently upgraded to unsupported operations.
    noop_id = 'fixture-ace-noop-' + uuid.uuid4().hex
    folder = ROOT / '.runtime/fixtures/complex' / noop_id
    folder.mkdir(parents=True)
    adapter = make_adapter('ace', noop_id, current, 'fixture-key', fixture_responses=[
        '{"bullet_tags":[]}', '{"reasoning":"No new observed insight","operations":[]}'])
    adapter.task(folder, {'run_id': noop_id, 'task_id': 'fixture-noop', 'attempt_id': noop_id + '.attempt-1', 'benchmark': 'babyai'})
    before = adapter.snapshot()['playbook']
    adapter.update(episode)
    assert adapter.snapshot()['playbook'].strip() == before.strip()
    checks.append({'method': 'ace', 'passed': True, 'legitimate_native_noop': True})
    report = {'schema_version': 'section7-observability-v2', 'passed': True, 'model_calls': 0,
              'local_embedding_calls_only_for_mem0': True, 'checks': checks,
              'limits': ['Fixed native replies certify mechanism/recording, not performance.',
                         'Online auxiliary-role transport and real model output still require the approved canary.']}
    save(ROOT / 'records/complex-fixture-acceptance.json', report)
    print(json.dumps({'passed': True, 'model_calls': 0, 'methods': ['mem0', 'awm', 'ace'], 'cases': len(checks)}))


if __name__ == '__main__':
    main()
