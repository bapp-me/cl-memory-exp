"""Run historical audits using only their pure helpers, without benchmark cache."""
import ast
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys
import types

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / 'experiments/agent_memory_plan_20261002'
tree = ast.parse((ROOT / 'core.py').read_text(encoding='utf-8'))
helpers = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {'digest', 'memory_context'}]
assert {n.name for n in helpers} == {'digest', 'memory_context'}
core = types.ModuleType('core')
core.__dict__.update(ROOT=ROOT, json=json, hashlib=hashlib, re=re)
exec(compile(ast.Module(body=helpers, type_ignores=[]), str(ROOT / 'core.py'), 'exec'), core.__dict__)

def save(path, value):
    # Write new verification output separately; never rewrite exported evidence.
    destination = REPO / 'docs/verification' / Path(path).name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

core.save = save
sys.modules['core'] = core
for name in ['audit_runs.py', 'audit_diagnostics.py']:
    runpy.run_path(str(ROOT / name), run_name='__main__')
