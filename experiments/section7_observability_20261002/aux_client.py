"""Recorded same-GLM calls for native memory roles; no task regeneration."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from runtime import ROOT, save, read, event, digest
from engine import event


class AuxiliaryCallError(RuntimeError):
    pass


class AuxClient:
    def __init__(self, config, api_key, fixture_responses=None):
        self.config = config
        self.api_key = api_key
        self.fixture_responses = fixture_responses
        self.out = None
        self.identity = None
        self.index = 0
        self.errors = []
        self.budget_events = []

    def task(self, out, identity):
        self.out = out
        self.identity = identity
        self.index = 0
        self.errors = []
        self.budget_events = []

    def call(self, messages, role, response_format=None):
        self.index += 1
        folder = self.out / 'auxiliary' / f'{self.index:03d}-{role}'
        folder.mkdir(parents=True)
        cfg = {**self.identity, 'out': str(folder), 'role': role,
               'call_prefix': self.identity['attempt_id'] + f'.{role}-{self.index}',
               'model': self.config['model']['api_id'], 'base_url': self.config['model']['base_url'],
               'messages': messages, 'response_format': response_format, 'memory_blocks': []}
        save(folder / 'input-public.json', cfg)
        event(self.out, 'auxiliary_call', role=role, folder=str(folder.relative_to(self.out)),
              attempt_id=self.identity['attempt_id'], input_hash=digest(messages))
        if self.fixture_responses is not None:
            value = self.fixture_responses.pop(0)
            save(folder / 'fixture-result.json', {'model_calls': 0, 'text': value, 'role': role})
            return value
        inputs = ROOT / '.runtime/inputs'
        input_path = inputs / (uuid.uuid4().hex + '.json')
        save(input_path, cfg)
        env = os.environ.copy()
        env['EXPERIMENT_API_KEY'] = self.api_key
        started = time.monotonic()
        try:
            process = subprocess.run(['node', str(ROOT / 'aux_runner.mjs'), str(input_path)], env=env,
                                     capture_output=True, timeout=210)
            result = read(folder / 'aux-result.json') if (folder / 'aux-result.json').exists() else {'error': 'Missing auxiliary terminal record'}
            if result.get('error') and 'Registered request byte budget exceeded' in result['error']:
                self.budget_events.append({'role': role, 'type': 'context_byte_budget_exceeded', 'folder': str(folder.relative_to(self.out))})
                event(self.out, 'auxiliary_budget_exhausted', role=role, reason='Registered 320000-byte request guard; no alternate prompt or retry',
                      generation_attempt=self.index, actual_http_attempts=0)
                return ''
            if process.returncode or result.get('error'):
                raise AuxiliaryCallError(result.get('error') or 'Auxiliary Node process failed')
            return result['text']
        except Exception as error:
            self.errors.append(type(error).__name__ + ': ' + str(error))
            save(folder / 'process-failure.json', {'role': role, 'error': self.errors[-1],
                 'seconds': time.monotonic() - started, 'usage': None})
            raise
        finally:
            input_path.unlink(missing_ok=True)
