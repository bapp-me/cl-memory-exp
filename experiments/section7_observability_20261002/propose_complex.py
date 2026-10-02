"""Reviewable next-stage settings, with explicit unimplemented adaptations."""
import json
from runtime import ROOT, read, save, digest


def main():
    common = read(ROOT / 'records/confirmed-config-v1.json')
    sources = read(ROOT / 'records/complex-source-audit.json')['sources']
    proposal = {
        'config_id': 'section7-complex-proposal-v1',
        'status': 'awaiting_user_confirmation_and_adapter_implementation',
        'online_started': False, 'user_confirmation': None,
        'common_confirmed_config': 'records/confirmed-config-v1.json',
        'common_confirmed_config_hash': digest(common),
        'unchanged_common_settings': {'model': common['model'], 'api_cap': 50,
            'solver_budgets': common['budgets'], 'data': common['data'], 'memory_injection_utf8_byte_cap': 48000},
        'scope': {'methods': ['mem0_classic_vector', 'awm_online_pi', 'ace_online_pi_official_add_only'],
            'task_executions': 36, 'per_method': 'Same preregistered 4 code tasks + full 8-task BabyAI family',
            'repetitions': 1, 'initial_memory': 'empty separately for every method and benchmark',
            'formal_96_task_stream_or_validation_or_final_test': False},
        'concurrency': {'global_inflight_api_cap': 50, 'max_active_methods': 3,
            'independent_online_streams': 6, 'within_each_online_stream': 1,
            'commit_all_memory_updates_before_next_task': True,
            'per_method_gate': 'Only launch this method after its offline/fixture checks pass; halt only affected stream on observation/infrastructure failure'},
        'auxiliary_model': {'api_id': 'glm-5.3-flash', 'reasoning_effort': 'high',
            'temperature': 'omitted, same provider default', 'max_output_tokens_per_call': 8192,
            'whole_call_timeout_seconds': 180, 'transport_extra_retries': 2,
            'correctness_or_invalid_json_regeneration': False, 'all_roles_and_failures_counted': True},
        'memory_source': 'Only own legitimate prompts, visible actions/tool feedback and submitted output; no hidden score, answer, tests, pairing labels or reasoning blocks',
        'mem0': {
            'package': 'mem0ai', 'version': '0.1.118', 'wheel_sha256': sources['mem0']['wheel_sha256'],
            'variant': 'Classic OSS vector memory; graph and reranker disabled; not current 2.x memory algorithm',
            'native_operations': ['ADD', 'UPDATE', 'DELETE', 'NONE'],
            'add': {'infer': True, 'frequency': 'after each submitted/completed task',
                'input': 'Own legal episode formatted as messages; native fact extraction and update prompts retained'},
            'search': {'query': 'current legal task prompt', 'limit': 5, 'threshold': None,
                'packing': 'Native similarity order; preserve complete facts within 48000-byte solver injection cap',
                'internal_update_neighbor_limit': 5,
                'limitation': 'Search limit 5 is an explicitly chosen project setting; the pinned public search API default is 100'},
            'embedding': {'provider': 'huggingface', 'model': sources['embedding']['model'],
                'revision': sources['embedding']['revision'], 'dimensions': 384, 'device': 'cpu',
                'max_seq_length': 256, 'normalization': 'Retain pinned model modules',
                'mode': 'local inference; no paid embedding API',
                'long_text_policy': 'Native 256-token truncation, logged; no query rewriting or custom chunking'},
            'storage': {'vector_store': 'local Qdrant, cosine', 'history': 'per-stream SQLite',
                'isolation': 'Distinct collection, path and logical user ID for every method/benchmark/repetition',
                'snapshots': 'Recoverable index/state plus native history/diffs; solver sandbox has no access'},
            'pending_work': ['Resolve and lock Python dependencies without invoking a model', 'Add role/embedding/native state observation hooks', 'Run native adapter fixtures']},
        'awm': {
            'repository': sources['awm']['repository'], 'revision': sources['awm']['revision'],
            'mode': 'online own-experience workflow induction; Pi solver adaptation',
            'induction_frequency_tasks': 1, 'writer_calls_per_update': 1,
            'induction_input': 'Cumulative legal past trajectories in this short stream; no author task-specific exemplars',
            'native_mechanism': 'Induce common multi-step subroutines, abstract task-specific arguments, avoid overlapping workflows',
            'representation': 'Native text workflow library; writer may legitimately output no reusable workflow',
            'solver_injection': 'Whole workflow blocks in library order up to 48000 UTF-8 bytes; no additional embedding/reranker',
            'overflow_policy': 'Drop oldest whole workflow blocks from injection, preserving underlying library and logged selection',
            'adaptations': ['Replace web action/environment vocabulary with the declared code/BabyAI tools',
                'No website dataset annotations, prewritten gold examples or hidden success filter',
                'Keep the native cumulative induction/library update rather than substituting episode retrieval'],
            'pending_work': ['Freeze adapted induction/solver prompt hashes', 'Implement workflow boundary/provenance logs', 'Run parsing/NOOP/overflow fixtures']},
        'ace': {
            'repository': sources['ace']['repository'], 'revision': sources['ace']['revision'],
            'mode': 'online Pi Generator + native Reflector + native Curator/deterministic playbook application',
            'no_ground_truth': True, 'reflector_frequency_tasks': 1, 'reflection_calls_per_task': 1,
            'curator_frequency_tasks': 1, 'curator_calls_per_task': 1,
            'reflector_inputs': 'Own submitted answer, visible action trace and legal tool feedback; no external correctness label',
            'playbook_operations_supported_by_this_revision': ['ADD', 'helpful/harmful/neutral counter updates', 'empty operations NOOP'],
            'playbook_operations_not_implemented_in_native_apply_function': ['UPDATE', 'MERGE', 'DELETE'],
            'optional_bulletpoint_analyzer': False, 'batched_proposal_aggregation': False,
            'playbook_prompt_token_budget': 80000,
            'token_budget_note': 'Native prompt-side budget, not a verified hard tokenizer limit for GLM; 320000-byte request guard remains in force',
            'solver_injection': 'Whole playbook bullets in native section order, within 48000 UTF-8 bytes',
            'overflow_policy': 'Exclude oldest whole bullets from solver injection only; log mapping and retain full playbook state',
            'adaptations': ['Pi supplies the Generator trajectory and declared tools',
                'Apply reflection/curation only after fixed submission; no new attempt on current task',
                'Use native NO_GT prompt variants and supported operations; disclose ADD-only limitation',
                'Record model bullet-use judgments as self-assessment, not causal evidence'],
            'pending_work': ['Adapt the Generator observation interface and freeze prompt hashes',
                'Connect native Reflector/Curator with recorded GLM calls', 'Run counter/delta/NOOP/readonly/source-isolation fixtures']},
        'approval_boundary': 'Confirm these new memory choices before any complex-method online/model/embedding inference; source audit alone is not adapter acceptance',
        'required_before_online': ['All adapter-specific fixture gates pass', 'Freeze adapted prompts, dependency locks and source/config hashes',
            'Record departures from original web/QA orchestration', 'Keep 36-task ceiling and no additional correctness retry'],
        'primary_sources': [
            'https://pypi.org/project/mem0ai/0.1.118/',
            'https://docs.mem0.ai/components/embedders/models/huggingface',
            'https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2',
            'https://github.com/zorazrw/agent-workflow-memory',
            'https://github.com/ace-agent/ace']
    }
    save(ROOT / 'records/complex-proposed-config-v1.json', proposal)
    acceptance = read(ROOT / 'records/online-acceptance.json')
    progress = {'section': '7.0', 'status': 'in_progress_complex_configuration_confirmation_pending',
        'whole_section_complete': False,
        '7.0.1': {'status': 'complete_for_four_proposed_legacy_first_pass_flows', 'tasks': 208, 'model_calls': 0},
        '7.0.2': {'status': 'common_recorder_and_simple_adapters_passed', 'fixture_checks': read(ROOT / 'records/fixture-acceptance.json')['checks'],
            'complex_specific_fixtures': 'pending implementation'},
        '7.0.3': {'status': 'first_three_methods_complete', 'tasks': 36, 'model_calls': acceptance['calls'],
            'unknown_usage_attempts': sum(r['unknown_usage_http_attempts'] for r in acceptance['summary']),
            'actual_api_peak': acceptance['observed_api_peak'], 'api_cap': 50},
        '7.0.4': {'status': 'simple_methods_accepted_with_explicit_passive_reconciliations', 'audit': 'records/online-acceptance.json',
            'frozen_original_sources': 'records/online-source-snapshot-v1.json',
            'post_run_changes': 'records/post-run-passive-repair.json', 'complex_methods': 'not accepted yet'},
        'next_stage': 'Confirm complex-proposed-config-v1.json; implement/fixture/freeze the three adapters then their 36-task acceptance batch',
        'section7.1_started': False,
        'performance_claim': 'Canary only; no method-ranking, causal transfer or stability conclusion'}
    save(ROOT / 'records/section7-progress.json', progress)
    print(json.dumps({'proposed_complex_tasks': 36, 'complex_online_started': False, 'simple_tasks_accepted': 36}))


if __name__ == '__main__':
    main()
