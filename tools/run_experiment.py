"""Run an existing experiment script with environment-only credentials."""
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]

def get_secret(provider):
    names = {'deepseek': 'DEEPSEEK_API_KEY', 'glm': 'GLM_API_KEY'}
    if provider not in names:
        raise ValueError('Unknown provider')
    value = os.environ.get(names[provider], '').strip()
    if not value:
        raise RuntimeError('Set ' + names[provider] + ' in your local environment')
    return value

def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python tools/run_experiment.py experiments/path/script.py [args]')
    script = (ROOT / sys.argv[1]).resolve()
    if not script.is_relative_to(ROOT / 'experiments') or script.suffix != '.py':
        raise SystemExit('Choose a Python script within experiments/')
    sys.path.insert(0, str(ROOT / 'experiments/memory_direction_20261002'))
    import lab_common
    lab_common.get_secret = get_secret
    sys.path.insert(0, str(script.parent))
    sys.argv = [str(script), *sys.argv[2:]]
    runpy.run_path(str(script), run_name='__main__')

if __name__ == '__main__':
    main()
