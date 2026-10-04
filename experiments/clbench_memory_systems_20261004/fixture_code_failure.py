"""No-model fault injection: stopped container must never become a score."""
import time
import uuid
from codebase_adapter import CodebaseStream
from prepare import ROOT, save

directory = ROOT / '.local/fixtures' / ('code-failure-' + uuid.uuid4().hex)
stream = CodebaseStream(directory)
save(ROOT / '.local/fixture-code-container.json', {'id': stream.task._env.container_id,
    'signal': str(directory / 'stopped'), 'directory': str(directory)})
print('Waiting for experiment-owned container stop', flush=True)
try:
    deadline = time.monotonic() + 180
    while not (directory / 'stopped').exists():
        if time.monotonic() > deadline: raise TimeoutError('Fixture injection missing')
        time.sleep(.2)
    try: stream.action({'command': 'true'})
    except RuntimeError as exc:
        assert 'infrastructure failure' in str(exc)
    else: raise AssertionError('Stopped container admitted as a business result')
    assert not list(stream.private.glob('result-*.json'))
    save(ROOT / 'records/codebase-failure-fixture.json', {'status': 'passed', 'model_calls': 0,
        'check': 'actual stopped container raises before any task result is admitted',
        'raw': directory.relative_to(ROOT).as_posix()})
    print('Stopped-container rejection passed', flush=True)
finally: stream.close()
