"""Native memory mechanisms with legitimate feedback and observation hooks."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from runtime import ROOT, read, save, digest, event
from engine import event
from aux_client import AuxClient, AuxiliaryCallError

os.environ['MEM0_DIR'] = str(ROOT / '.runtime/mem0-meta')
os.environ['MEM0_TELEMETRY'] = 'false'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HOME'] = str(ROOT / '.cache/hf')
os.environ['USE_TF'] = '0'
os.environ['USE_FLAX'] = '0'
sys.path.insert(0, str(ROOT / '.runtime/complex-libs'))
SOURCES = ROOT / '.cache/complex-sources'


def pure_functions(path, names=None, globals_extra=None):
    namespace = {'re': re, 'json': json, 'Dict': Dict, 'List': List, 'Optional': Optional, 'Any': Any, 'Tuple': Tuple, 'Path': Path}
    if globals_extra:
        namespace.update(globals_extra)
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and (names is None or node.name in names)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def pack(entries, query, ranked=False):
    selected = copy.deepcopy(entries)
    dropped = []
    while selected and len(json.dumps(selected, ensure_ascii=False).encode()) > 48000:
        item = selected.pop(-1 if ranked else 0)
        dropped.append({'memory_id': item['memory_id'], 'reason': 'lowest_rank_byte_budget' if ranked else 'oldest_complete_block_byte_budget'})
    return selected, {'query_sha256': hashlib.sha256(query.encode()).hexdigest(),
        'observable_candidates': [{'memory_id': entry['memory_id'], 'rank': i + 1, 'score': entry.get('score')}
                                  for i, entry in enumerate(entries)],
        'selected_before_packing': [entry['memory_id'] for entry in entries], 'dropped': dropped,
        'injected_ids': [entry['memory_id'] for entry in selected], 'injected_hash': digest(selected),
        'injected_utf8_bytes': len(json.dumps(selected, ensure_ascii=False).encode()),
        'token_count': None, 'token_measurement_method': 'unavailable'}


class Adapter:
    def __init__(self, method, run_id, config, api_key, fixture_responses=None):
        self.method, self.run_id, self.config = method, run_id, config
        self.aux = AuxClient(config, api_key, fixture_responses)
        self.identity = None
        self.out = None
        self.state = {'episode_count': 0, 'provenance': {}}

    def task(self, out, identity):
        self.out, self.identity = out, identity
        self.aux.task(out, identity)

    def snapshot(self):
        return copy.deepcopy(self.state)

    def restore(self, state):
        self.state = copy.deepcopy(state)

    def restore_checkpoint(self, folder, state):
        self.restore(state)

    def after_update(self, before, operations):
        if self.aux.errors:
            raise AuxiliaryCallError('; '.join(self.aux.errors))
        after = self.snapshot()
        save(self.out / 'native-operations.json', {'method': self.method, 'operations': operations,
             'source_event_ids': [self.identity['attempt_id']], 'before_hash': digest(before), 'after_hash': digest(after)})
        event(self.out, 'memory_event', operation='native_update' if operations else 'noop',
              before_hash=digest(before), after_hash=digest(after), source_event_ids=[self.identity['attempt_id']],
              reason=None if operations else 'Native method produced no learned-entry mutation')
        return after

    def close(self):
        pass


class AWMMemory(Adapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state.update(episodes=[], source_attempts=[], workflow_text='')
        native = pure_functions(SOURCES / 'awm/mind2web/utils/data.py', {'format_examples', 'is_website_header', 'filter_workflows'})
        self.format_examples, self.filter_workflows = native['format_examples'], native['filter_workflows']
        instruction = (SOURCES / 'awm/mind2web/prompt/instruction_action.txt').read_text(encoding='utf-8')
        self.instruction = instruction.replace('web nagivation', 'agent tool-use') + (
            '\nUse only the given legal observations, not hidden correctness. The declared actions are PYTHON/SUBMIT for code or ACTION for navigation. '
            'Abstract example-specific values into parameters. Return complete Markdown workflows, each starting with ## Workflow <name>, '
            'with a goal and at least two numbered steps. No prewritten task answer. If no reusable workflow can be induced, return NO_WORKFLOW.')

    @staticmethod
    def blocks(text):
        return [block.strip() for block in re.split(r'(?m)(?=^## Workflow\b)', text) if block.strip()]

    def retrieve(self, prompt):
        entries = [{'memory_id': digest(block), 'text': block} for block in self.blocks(self.state['workflow_text'])]
        return pack(entries, prompt)

    def update(self, episode):
        before = self.snapshot()
        self.state['episodes'].append(episode)
        self.state['source_attempts'].append(self.identity['attempt_id'])
        examples = []
        for historical in self.state['episodes']:
            data = json.loads(historical['text'])
            examples.append({'confirmed_task': data['task'], 'action_reprs': [json.dumps(item, ensure_ascii=False) for item in data['trajectory']]})
        prompt = self.instruction + '\n\n' + self.format_examples(examples, suffix='# Summary Workflows')
        response = self.aux.call([{'role': 'user', 'content': prompt}], 'writer')
        filtered = self.filter_workflows(response, self.identity['benchmark'])
        save(self.out / 'writer-candidate.json', {'raw_response': response, 'native_filtered': filtered,
             'source_event_ids': self.state['source_attempts'], 'instruction_hash': hashlib.sha256(self.instruction.encode()).hexdigest()})
        operations = []
        if filtered.strip() and filtered.strip() != 'NO_WORKFLOW':
            self.state['workflow_text'] = filtered
            for block in self.blocks(filtered):
                self.state['provenance'][digest(block)] = self.state['source_attempts'][:]
            operations.append({'type': 'REPLACE_WORKFLOW_LIBRARY', 'before_content_hash': digest(before['workflow_text']),
                               'after_content_hash': digest(filtered), 'source_event_ids': self.state['source_attempts'][:]})
        self.state['episode_count'] += 1
        return self.after_update(before, operations)


class ACEMemory(Adapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state.update(playbook='## STRATEGIES & INSIGHTS\n\n## COMMON MISTAKES TO AVOID\n\n## OTHERS\n', next_id=1)
        self.last_injected = []
        utilities = pure_functions(SOURCES / 'ace/utils.py', {'get_section_slug'})
        helpers = pure_functions(SOURCES / 'ace/playbook_utils.py', globals_extra={'get_section_slug': utilities['get_section_slug']})
        self.helpers = helpers
        namespace = {**helpers, 'Dict': Dict, 'List': List, 'Tuple': Tuple, 'Optional': Optional, 'Any': Any, 'Path': Path}
        for path in ['ace/prompts/reflector.py', 'ace/prompts/curator.py']:
            exec(compile((SOURCES / 'ace' / path).read_text(encoding='utf-8'), path, 'exec'), namespace)

        def notice(*values, **kwargs):
            if self.out:
                event(self.out, 'native_notice', text=' '.join(str(value) for value in values))

        def call(client, provider, model, prompt, role, call_id, max_tokens, log_dir, use_json_mode=False):
            text = self.aux.call([{'role': 'user', 'content': prompt}], role,
                                 {'type': 'json_object'} if use_json_mode else None)
            return text, {'call_id': call_id, 'role': role, 'recorded_aux_index': self.aux.index}

        namespace.update(print=notice, timed_llm_call=call,
            log_curator_operation_diff=lambda *args, **kwargs: None,
            log_curator_failure=lambda *args, **kwargs: event(self.out, 'native_curator_reject', reason=str(args)))
        # Helper functions also need the same non-disruptive logging namespace.
        for value in list(helpers.values()):
            if callable(value) and getattr(value, '__globals__', None) is helpers:
                value.__globals__['print'] = notice
        for name, path in [('Reflector', 'ace/core/reflector.py'), ('Curator', 'ace/core/curator.py')]:
            tree = ast.parse((SOURCES / 'ace' / path).read_text(encoding='utf-8'))
            node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
            exec(compile(ast.Module(body=[node], type_ignores=[]), path, 'exec'), namespace)
        self.reflector = namespace['Reflector'](None, 'openai', 'glm-5.3-flash', 8192)
        self.curator = namespace['Curator'](None, 'openai', 'glm-5.3-flash', 8192)

    def retrieve(self, prompt):
        entries = []
        section = None
        for line in self.state['playbook'].splitlines():
            if line.startswith('##'):
                section = line[2:].strip()
            parsed = self.helpers['parse_playbook_line'](line)
            if parsed:
                entries.append({'memory_id': parsed['id'], 'section': section, 'text': line})
        selected, record = pack(entries, prompt)
        self.last_injected = selected
        return selected, record

    def update(self, episode):
        before = self.snapshot()
        data = json.loads(episode['text'])
        trace = json.dumps(data['trajectory'], ensure_ascii=False)
        tool_observations = [item for item in data['trajectory'] if isinstance(item, dict) and 'tool' in item]
        predicted = next((item['arguments']['code'] for item in reversed(data['trajectory']) if isinstance(item, dict)
                          and item.get('type') == 'toolCall' and item.get('name') == 'SUBMIT'), 'No separate textual answer; use visible actions.')
        reflection, tags, call_info = self.reflector.reflect(question=data['task'], reasoning_trace=trace,
            predicted_answer=predicted, ground_truth=None, environment_feedback=json.dumps(tool_observations, ensure_ascii=False),
            bullets_used='Available to Generator; actual use is unconfirmed:\n' + '\n'.join(entry['text'] for entry in self.last_injected),
            use_ground_truth=False, use_json_mode=False,
            call_id=self.identity['attempt_id'] + '.reflector', log_dir=str(self.out / 'auxiliary'))
        save(self.out / 'reflection.json', {'content': reflection, 'bullet_tags': tags, 'ground_truth': None,
             'quality_status': 'model self-assessment only', 'source_event_ids': [self.identity['attempt_id']]})
        counted = self.helpers['update_bullet_counts'](self.state['playbook'], tags)
        stats = {'bullets': len([line for line in counted.splitlines() if self.helpers['parse_playbook_line'](line)])}
        playbook, next_id, operations, info = self.curator.curate(current_playbook=counted,
            recent_reflection=reflection, question_context=data['task'], current_step=self.state['episode_count'] + 1,
            total_samples=self.config.get('stream_tasks', 12), token_budget=80000, playbook_stats=stats,
            use_ground_truth=False, use_json_mode=False, call_id=self.identity['attempt_id'] + '.curator',
            log_dir=str(self.out / 'auxiliary'), next_global_id=self.state['next_id'])
        previous_ids = {parsed['id'] for line in self.state['playbook'].splitlines()
                        if (parsed := self.helpers['parse_playbook_line'](line))}
        self.state.update(playbook=playbook, next_id=next_id)
        for line in playbook.splitlines():
            parsed = self.helpers['parse_playbook_line'](line)
            if parsed and parsed['id'] not in previous_ids:
                self.state['provenance'][parsed['id']] = [self.identity['attempt_id']]
        self.state['episode_count'] += 1
        journal = [{'type': 'COUNTER_TAGS', 'tags': tags}] if tags else []
        journal.extend(operations)
        return self.after_update(before, journal)


class Mem0Memory(Adapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from mem0 import Memory
        environment = read(ROOT / 'records/complex-environment.json')
        self.folder = ROOT / '.runtime/mem0-state' / self.run_id
        self.folder.mkdir(parents=True, exist_ok=True)
        self.native = Memory.from_config({'version': 'v1.1',
            'llm': {'provider': 'openai', 'config': {'model': 'glm-5.3-flash', 'api_key': 'not-used-by-recorded-bridge'}},
            'embedder': {'provider': 'huggingface', 'config': {'model': environment['local_path'],
                         'embedding_dims': 384, 'model_kwargs': {'device': 'cpu', 'trust_remote_code': False}}},
            'vector_store': {'provider': 'qdrant', 'config': {'collection_name': 'memory', 'path': str(self.folder / 'vectors'), 'embedding_model_dims': 384}},
            'history_db_path': str(self.folder / 'history.sqlite')})
        assert self.native.enable_graph is False
        self.user = self.run_id
        self.original_embed = self.native.embedding_model.embed
        self.operations = []

        owner = self

        class RecordedLLM:
            def generate_response(self, messages, response_format=None, tools=None, **kwargs):
                role = 'writer' if owner.aux.index == 0 else 'curator'
                text = owner.aux.call(messages, role, response_format)
                event(owner.out, 'native_llm_response', role=role, text_sha256=hashlib.sha256(text.encode()).hexdigest())
                return text

        self.native.llm = RecordedLLM()

        def embed(text, memory_action=None, **kwargs):
            started = time.monotonic()
            result = self.original_embed(text, memory_action, **kwargs)
            if self.out:
                event(self.out, 'embedding_call', role='embedding', provider='local_huggingface',
                      model=environment['embedding_model'], revision=environment['revision'],
                      input_sha256=hashlib.sha256(text.encode()).hexdigest(), input_utf8_bytes=len(text.encode()),
                      max_seq_length=256, dimensions=len(result), seconds=time.monotonic() - started,
                      vector_sha256=digest(result), billed_api_call=False)
            return result

        self.native.embedding_model.embed = embed
        for method, operation in [('_create_memory', 'ADD'), ('_update_memory', 'UPDATE'), ('_delete_memory', 'DELETE')]:
            original = getattr(self.native, method)

            def observed(*args, _original=original, _operation=operation, **kwargs):
                result = _original(*args, **kwargs)
                record = {'type': _operation, 'args': args, 'kwargs': kwargs, 'native_return': result,
                          'source_event_ids': [self.identity['attempt_id']]}
                self.operations.append(record)
                event(self.out, 'native_memory_operation', **record)
                return result

            setattr(self.native, method, observed)

    def snapshot(self):
        points = []
        offset = None
        while True:
            batch, offset = self.native.vector_store.client.scroll(collection_name='memory', limit=256,
                offset=offset, with_payload=True, with_vectors=True)
            points.extend(point.model_dump(mode='json') for point in batch)
            if offset is None:
                break
        return {**copy.deepcopy(self.state), 'points': sorted(points, key=lambda point: str(point['id']))}

    def restore(self, state):
        from qdrant_client.models import PointStruct
        current = self.snapshot()['points']
        points = state.get('points', [])
        if digest(current) == digest(points):
            self.state = {key: copy.deepcopy(value) for key, value in state.items() if key != 'points'}
            return
        if current:
            self.native.vector_store.client.delete(collection_name='memory', points_selector=[point['id'] for point in current])
        if points:
            self.native.vector_store.client.upsert(collection_name='memory', points=[PointStruct(id=point['id'], vector=point['vector'], payload=point['payload']) for point in points])
        self.state = {key: copy.deepcopy(value) for key, value in state.items() if key != 'points'}

    def retrieve(self, prompt):
        results = self.native.search(prompt, user_id=self.user, limit=5, threshold=None)['results']
        entries = [{'memory_id': entry['id'], 'text': entry['memory'], 'score': entry.get('score')} for entry in results]
        selected, record = pack(entries, prompt, ranked=True)
        record['candidate_scope'] = 'Native Qdrant top-5 returned set; complete persisted point pool separately snapshotted'
        return selected, record

    def restore_checkpoint(self, folder, state):
        self.restore(state)
        path = folder / 'native-history-after.sqlite'
        if path.exists():
            source = sqlite3.connect(path)
            destination = sqlite3.connect(self.folder / 'history.sqlite')
            source.backup(destination)
            source.close(); destination.close()

    def update(self, episode):
        before = self.snapshot()
        self.operations = []
        data = json.loads(episode['text'])
        messages = [{'role': 'user', 'content': data['task']},
                    {'role': 'assistant', 'content': json.dumps(data['trajectory'], ensure_ascii=False)}]
        result = self.native.add(messages, user_id=self.user, infer=True)
        save(self.out / 'native-add-result.json', result)
        self.state['episode_count'] += 1
        after = self.snapshot()
        old_by_id = {point['id']: point for point in before['points']}
        for point in after['points']:
            if old_by_id.get(point['id']) != point:
                prior = self.state['provenance'].get(str(point['id']), [])
                self.state['provenance'][str(point['id'])] = sorted(set(prior + [self.identity['attempt_id']]))
        source = sqlite3.connect(self.folder / 'history.sqlite')
        destination = sqlite3.connect(self.out / 'native-history-after.sqlite')
        source.backup(destination)
        source.close(); destination.close()
        return self.after_update(before, self.operations)

    def close(self):
        self.native.vector_store.client.close()


def make_adapter(method, run_id, config, api_key, fixture_responses=None):
    cls = {'mem0': Mem0Memory, 'awm': AWMMemory, 'ace': ACEMemory}[method]
    return cls(method, run_id, config, api_key, fixture_responses=fixture_responses)
