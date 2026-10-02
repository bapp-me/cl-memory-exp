"""Prepare fixed local assets and record the human-confirmed configuration."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
LEGACY = REPO / 'experiments/agent_memory_plan_20261002'
ORIGINAL = Path('D:/campus_re/experiments/agent_memory_plan_20261002')


def main():
    config = json.loads((ROOT / 'records/proposed-config.json').read_text(encoding='utf-8'))
    config['config_id'] = 'section7-observability-confirmed-v1'
    config['status'] = 'user_confirmed_pending_fixture_and_environment_gates'
    config['user_confirmation'] = {'client_date': '2026-10-02', 'timezone': 'Asia/Hong_Kong',
        'instruction': 'api的同时请求数量最高为50，我的电脑资源也够用，尽可能把上限拉高吧。其他都没问题，开始吧'}
    config['runtime']['concurrency_proposal'].update(global_inflight_model_or_embedding_requests=50,
        max_active_methods=3, independent_no_memory_tasks_parallel=True,
        theoretical_first_batch_max_active_tasks=16,
        automatic_concurrency_increase=True)
    config['runtime']['concurrency_proposal']['parallel_units'] = ['12 independent No Memory tasks', '4 separate online memory streams']
    config['budgets']['monetary_hard_limit_status'] = 'User confirmed no hard monetary cap for this 36-task batch'
    config['acceptance']['schema_version'] = 'section7-observability-v1'
    config['runtime']['pi_runtime_path'] = str(REPO / 'experiments/memory_scope_fix_20261002/.runtime/pi')
    config['runtime']['babyai_libraries_path'] = str(ORIGINAL / '.runtime/babyai-libs')
    files = []
    sources = json.loads((LEGACY / 'records/source-assets.json').read_text(encoding='utf-8'))
    needed = ['.cache/agentcl-codeeval.json', '.cache/agentcl-babyai.jsonl', '.cache/agentboard/agentboard_environment_babyai_env.py']
    for name in needed:
        source = ORIGINAL / name
        raw = source.read_bytes()
        expected = next(item['sha256'] for item in sources if item['path'] == name)
        actual = hashlib.sha256(raw).hexdigest()
        assert actual == expected, name
        target = ROOT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        files.append({'name': name, 'sha256': actual, 'bytes': len(raw)})
    (ROOT / '.runtime').mkdir(exist_ok=True)
    shell = (LEGACY / 'sandbox.sh').read_bytes()
    (ROOT / '.runtime/sandbox.sh').write_bytes(shell)
    shutil.copyfile(LEGACY / 'records/scorer-issues.json', ROOT / 'records/scorer-issues.json')
    target = ROOT / 'records/confirmed-config-v1.json'
    if target.exists():
        assert json.loads(target.read_text(encoding='utf-8')) == config, 'Confirmed config conflict'
    else:
        target.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report = {'model_calls': 0, 'assets': files, 'sandbox_shell_sha256': hashlib.sha256(shell).hexdigest(),
              'pi_versions': {name: json.loads((Path(config['runtime']['pi_runtime_path']) / 'node_modules/@earendil-works' / name / 'package.json').read_text(encoding='utf-8'))['version']
                              for name in ['pi-agent-core', 'pi-ai']}}
    assert all(v == '1.0.0' for v in report['pi_versions'].values())
    (ROOT / 'records/environment-preparation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
