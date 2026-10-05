"""Mechanical audit of real Codex continuation; no business-content review."""
from datetime import datetime, timezone
from prepare import ROOT, read, save, sha
from native_evidence import archive, validate


def main():
    streams = []
    for run in ['formal-db-codex-r1', 'candidate-code-codex-64k-v1']:
        directory = ROOT/'private-runs'/run
        results = read(directory/'results.json')
        inspected = []
        for row in results:
            plan = row.get('consolidation_schedule')
            if not plan:
                continue
            out = directory/f"task-{row['index']:03d}"
            snapshot = out/('recovered-native-state.tar.gz' if row.get('recovered_maintenance') else 'native-state.tar.gz')
            evidence = validate(archive(snapshot), out.name, 'codex', row['session_id'])
            barrier = read(out/'barrier.json')
            expected = {'completed_changed','completed_noop'} if plan['consolidation_required'] else {'completed_staged'}
            assert barrier['status'] in expected and barrier['durable']
            assert read(out/'memory-before.json') == read(directory/f"task-{row['index']-1:03d}"/'memory-after.json')
            assert {x['thread_id'] for x in evidence['jobs']['extracted_sources']} <= {x['session_id'] for x in results[:row['index']+1]}
            since = read(out/'recovery-provenance.json')['recovery_started_at'] if row.get('recovered_maintenance') else None
            new_calls = []; writers = set()
            for path in (out/'requests').glob('*.attempt.json'):
                meta = read(path)
                if since and meta['timestamp'] < since:
                    continue
                q = read(path.with_name(path.name.replace('.attempt.json','.native-request.json')))
                wire = read(path.with_name(path.name.replace('.attempt.json','.request.json')))
                assert wire.get('max_output_tokens') == 65536
                new_calls.append(meta['attempt_id'])
                if q.get('client_metadata',{}).get('x-openai-subagent') == 'memory_consolidation':
                    writers.add(q['client_metadata']['thread_id'])
            if not plan['consolidation_required']:
                assert not writers, 'Consolidation called between batch boundaries'
            inspected.append({'position':plan['position'],'schedule':plan,'barrier_status':barrier['status'],
                'new_attempts':len(new_calls),'consolidation_agent_threads':len(writers),
                'extracted_sources':len(evidence['jobs']['extracted_sources']),
                'snapshot_sha256':sha(snapshot),'recovered_maintenance':row.get('recovered_maintenance',False)})
        streams.append({'run_id':run,'completed':len(results),'inspected':inspected,
            'real_deferred_boundary_verified':any(not x['schedule']['consolidation_required'] for x in inspected),
            'real_batch_consolidation_verified':any(x['schedule']['consolidation_required'] for x in inspected)})
    report={'as_of':datetime.now(timezone.utc).isoformat(),'status':'observed_prefix_passed','model_calls':0,
            'all_both_paths_observed':all(s['real_deferred_boundary_verified'] and s['real_batch_consolidation_verified'] for s in streams),
            'historical_rows_changed':False,'streams':streams}
    save(ROOT/'records/codex-batch-online-audit.json',report)
    print(report)


if __name__=='__main__':main()
