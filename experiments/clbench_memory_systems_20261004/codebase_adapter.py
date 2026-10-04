"""Official code task + grader using the credential-free Docker transport bridge."""
from __future__ import annotations
import os
from pathlib import Path
import shlex
import sys
import tempfile
import uuid
from prepare import ROOT, UPSTREAM, read, save
os.environ['MSWEA_GLOBAL_CONFIG_DIR'] = str(ROOT / '.local/mswea-config')
os.environ['MSWEA_SILENT_STARTUP'] = '1'
sys.path.insert(0, str(UPSTREAM))
from src.interface import Response
from src.tasks.codebase_adaptation.task import CodebaseAdaptationTask, BashCommandResponse
from src.tasks.codebase_adaptation.evaluator import evaluate_submission
from docker_dispatch import install, broker


def restore_rollout_context(task, index):
    """Recover the real previous stage before deciding whether to announce it."""
    task._stage_change_notice = None
    if index > 0:
        task._update_rollout_context_for_issue(index - 1, announce=False)
    task._update_rollout_context_for_issue(index, announce=index > 0)


class CodebaseStream:
    def __init__(self, directory, *, restore=False):
        self.directory = Path(directory); self.directory.mkdir(parents=True, exist_ok=True)
        self.private = self.directory / 'evaluator-private'; self.private.mkdir(exist_ok=True)
        tempfile.tempdir = str(self.private)
        os.chdir(UPSTREAM)
        install()
        self.task = CodebaseAdaptationTask(schedule='default')
        initialize = self.task._initialize_generic_pr_workspace
        def initialize_without_future_refs(instance):
            initialize(instance)
            if instance.raw_data.get('init_submodules'):
                raise RuntimeError('Submodule history isolation needs separate acceptance')
            command = """set -e
before=$(git rev-parse HEAD)
git for-each-ref --format='%(refname)' | while IFS= read -r ref; do
  if ! git merge-base --is-ancestor "$ref" HEAD 2>/dev/null; then
    git update-ref --no-deref -d "$ref"
  fi
done
git reflog expire --expire=now --all
git gc --prune=now
test "$(git rev-parse HEAD)" = "$before"
git for-each-ref --format='%(refname)' | while IFS= read -r ref; do
  git merge-base --is-ancestor "$ref" HEAD
done
git rev-parse HEAD
git status --short
"""
            audit = broker({'op': 'exec', 'container_id': self.task._env.container_id,
                            'cwd': instance.raw_data.get('workdir', '/testbed'), 'command': command})
            save(self.private / f'git-isolation-{instance.instance_id}.json', audit)
            if audit['returncode'] or instance.raw_data['base_commit'] not in audit['stdout']:
                raise RuntimeError('Code worktree future-history isolation failed')
        self.task._initialize_generic_pr_workspace = initialize_without_future_refs
        self.query = self.task.reset()
        expected = read(ROOT / 'records/task-manifest.json')['codebase_adaptation']
        if [q.instance_id for q in self.task.instances] != [q['instance_id'] for q in expected]:
            raise RuntimeError('Codebase order differs from lock')
        from src.tasks.codebase_adaptation import task as task_module
        original_evaluate = evaluate_submission
        def record_submission(model_patch, instance, **kwargs):
            index = next(i for i, row in enumerate(self.task.instances) if row.instance_id == instance['instance_id'])
            (self.private / f'submission-{index:03d}.diff').write_text(model_patch, encoding='utf-8', newline='')
            return original_evaluate(model_patch, instance, **kwargs)
        task_module.evaluate_submission = record_submission
        if restore and (self.private / 'state.json').exists():
            state = read(self.private / 'state.json')
            if state['current_steps']:
                raise RuntimeError('Interrupted code issue requires its saved workspace; do not restart business work')
            self.task.current_issue_idx = state['current_issue_idx']
            self.task.issue_history = state['issue_history']
            self.task.current_steps = 0
            if self.task.current_issue_idx < len(self.task.instances):
                restore_rollout_context(self.task, self.task.current_issue_idx)
                self.task._start_container()
                self.query = self.task.build_current_query()

    def public_query(self):
        q = self.query
        return {'prompt': q.prompt, 'index': q.instance_index, 'instance_id': q.instance_id,
                'project_key': self.task.instances[self.task.current_issue_idx].repo}

    def action(self, value):
        import docker_dispatch
        docker_dispatch.LAST_INFRASTRUCTURE_ERROR = None
        index = self.task.current_issue_idx
        action = BashCommandResponse(thought=value.get('thought', ''), command=value['command'])
        result = self.task.step(Response(action=action))
        if docker_dispatch.LAST_INFRASTRUCTURE_ERROR:
            save(self.private / 'infrastructure-failure.json', docker_dispatch.LAST_INFRASTRUCTURE_ERROR)
            raise RuntimeError('Code container infrastructure failure; no result admitted')
        self.query = result.next_query
        if result.observation.instance_complete:
            record = self.task.issue_history[-1]
            save(self.private / f'result-{index:03d}.json', {'record': record,
                'outcome': result.instance_outcome.__dict__ if result.instance_outcome else None})
            # Official trace already freezes model_patch before grading.
            save(self.private / f'trace-{index:03d}.json', [entry for entry in self.task.interaction_trace if entry['issue_index'] == index])
        save(self.private / 'state.json', {'current_issue_idx': self.task.current_issue_idx,
             'current_steps': self.task.current_steps, 'issue_history': self.task.issue_history})
        return {'observation': result.observation.content, 'instance_complete': result.observation.instance_complete,
                'done': result.done}

    def submission_artifact(self, index):
        from prepare import sha
        path = self.private / f'submission-{index:03d}.diff'
        return {'path': path.relative_to(self.directory).as_posix(), 'sha256': sha(path)} if path.exists() else None

    def close(self): self.task._cleanup_container()


def main():
    directory = ROOT / '.local/fixtures' / ('codebase-' + uuid.uuid4().hex)
    stream = CodebaseStream(directory)
    try:
        q = stream.public_query()
        row = stream.task.instances[0].raw_data
        result = stream.action({'command': 'git rev-parse HEAD'})
        assert row['base_commit'] in result['observation']
        assert stream.task.current_steps == 1 and not result['instance_complete']
        result = stream.action({'command': 'exit 7'})
        assert stream.task.current_steps == 2 and not result['instance_complete']
        env = stream.task._env
        # Direct fixture-only inspection; this path is never exposed as an agent tool.
        diff = broker({'op': 'exec', 'container_id': env.container_id,
                       'cwd': '/testbed', 'command': 'git diff --stat; git status --short'})
        save(directory / 'initial-test-patch-check.json', diff)
        assert diff['returncode'] == 0 and diff['stdout'].strip()
        controls = []
        for repo in ['jazzband/tablib', 'jd/tenacity']:
            instance = next(x for x in stream.task.instances if x.repo == repo)
            outcome = evaluate_submission(instance.patch, instance.raw_data)
            controls.append({'instance_id': instance.instance_id, 'repo': repo,
                             'success': outcome.success, 'status': outcome.status, 'error': outcome.error})
        save(directory / 'reference-controls.json', controls)
        assert all(x['success'] for x in controls), controls
        # Empty business changes: tests alone may appear in git diff, but the official
        # evaluator removes those paths and re-applies pristine test_patch itself.
        result = stream.action({'command': 'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'})
        assert result['instance_complete'] and stream.task.current_issue_idx == 1
        next_query = stream.public_query()
        assert next_query['instance_id'] != q['instance_id']
        next_commit = stream.action({'command': 'git rev-parse HEAD'})
        assert stream.task.instances[1].raw_data['base_commit'] in next_commit['observation']
        save(ROOT / 'records/codebase-fixtures.json', {'status': 'passed', 'model_calls': 0,
            'checks': ['official base commits', 'command budget counting including failures',
                       'test_patch visible as authorized', 'two-repo official reference grading',
                       'official submission sentinel', 'fresh next-issue container'],
            'reference_controls': [{k:v for k,v in x.items() if k != 'error'} for x in controls],
            'raw': directory.relative_to(ROOT).as_posix(), 'formal_ready': False})
        print({'codebase_fixtures': 'passed', 'model_calls': 0})
    finally: stream.close()


if __name__ == '__main__': main()
