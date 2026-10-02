"""Local, no-model-call evidence and installation inventory checks."""
import ast
import gzip
import hashlib
import json
import subprocess
from lab_common import ROOT, get_secret, save_json

checked=[]
for p in ROOT.glob('*.py'):
    ast.parse(p.read_text(encoding='utf-8'));checked.append(p.name)
keys=[get_secret(p).encode() for p in ('glm','deepseek')]
paths=[*ROOT.glob('*.py'),*ROOT.glob('*.md'),*ROOT.glob('*.json'),*ROOT.glob('*.txt'),
       *[p for p in (ROOT/'results').rglob('*') if p.is_file()],
       *[p for p in (ROOT/'fixtures').rglob('*') if p.is_file()]]
leaks=[]
for p in paths:
    data=p.read_bytes()
    if p.suffix=='.gz':data=gzip.decompress(data)
    if any(key in data for key in keys):leaks.append(str(p.relative_to(ROOT)))
assert not leaks, 'Credential-bearing files found; do not stage results'
digest=hashlib.file_digest((ROOT/'.cache/clbench/products.db').open('rb'),'sha256').hexdigest()
assert digest=='edf8ee80ff125de0bfd6c37a1d185efa9e3037ce28eb1bd1d32ae0829bd264a6'
guard=[]
for name,path,expected in [('inside',ROOT/'workspaces/guard-test/memory/test.md','allow'),
                           ('gold',ROOT/'.cache/clbench/questions.json','deny'),
                           ('credentials',ROOT/'.private/credentials.json','deny')]:
    r=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),str(ROOT/'file_guard.py'),str(ROOT/'workspaces/guard-test')],
                     input=json.dumps({'tool_name':'Read','tool_input':{'file_path':str(path)}}),capture_output=True,text=True)
    decision=json.loads(r.stdout)['hookSpecificOutput']['permissionDecision']
    assert decision==expected
    guard.append({'case':name,'decision':decision})
save_json(ROOT/'results/checkpoint-audit.json',{'syntax_checked':checked,'credential_scan_file_count':len(paths),
    'credentials_found':False,'db_sha256_unchanged':digest,'file_guard':guard,
    'limitation':'Guard invocation tested locally; not a paid adversarial evaluation of the Agent.'})

manifest=json.loads((ROOT/'installation-manifest.json').read_text(encoding='utf-8'))
source=ROOT/'.runtime/hermes-source'
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
facts_path=next((ROOT/'.runtime/hermes-home/installs').glob('*/facts.json'))
facts=json.loads(facts_path.read_text(encoding='utf-8'))
venv=facts['packages']['venv']['environment']
py=str(__import__('pathlib').Path(venv)/'Scripts/python.exe')
code='import importlib.metadata as m,json; print(json.dumps(sorted([{ "name":d.metadata["Name"],"version":d.version} for d in m.distributions()],key=lambda x:x["name"].lower())))'
experiment_packages=json.loads(subprocess.check_output([str(ROOT/'.venv/Scripts/python.exe'),'-c',code],text=True,encoding='utf-8'))
save_json(ROOT/'experiment-python-packages.json',experiment_packages)
manifest['experiment_python_packages_file']='experiment-python-packages.json'
manifest['experiment_python_package_count']=len(experiment_packages)
packages=json.loads(subprocess.check_output([py,'-c',code],text=True,encoding='utf-8'))
save_json(ROOT/'hermes-python-packages.json',packages)
tool_facts=json.loads((ROOT/'.runtime/hermes-tools/facts.json').read_text(encoding='utf-8'))
environments=[]
for exe in sorted((ROOT/'.runtime/hermes-home/installs').glob('*/environments/*/venv/Scripts/python.exe')):
    deps=json.loads(subprocess.check_output([str(exe),'-c',code],text=True,encoding='utf-8'))
    environments.append({'python':str(exe),'kind':'application','packages':deps})
for exe in sorted((ROOT/'.runtime/hermes-home/installs').glob('*/pm-runtime/generations/*/Scripts/python.exe')):
    deps=json.loads(subprocess.check_output([str(exe),'-c',code],text=True,encoding='utf-8'))
    environments.append({'python':str(exe),'kind':'package manager','packages':deps})
save_json(ROOT/'hermes-all-environments.json',environments)
manifest['hermes']={'source_commit':commit,'source_directory':str(source),'status':'SQL and native memory/history experiments verified',
    'python_executable':py,'python_package_count':len(packages),'python_packages_file':'hermes-python-packages.json',
    'all_preserved_environment_generations_file':'hermes-all-environments.json','preserved_environment_count':len(environments),
    'tools':tool_facts['packages'],'installer_attempt':'official PowerShell repository stage failed TLS; git OpenSSL clone then official pm.cli install succeeded',
    'command':'python -m pm.cli install --without agent-browser --without cua-driver',
    'extra_command':'python -m pm.cli install --extra anthropic',
    'isolated_environment':['HERMES_HOME','HERMES_RUNTIME_DIR','LOCALAPPDATA','UV_CACHE_DIR'],
    'global_path_modified':False,'browser_installed':False,'computer_use_installed':False}
manifest['hermes']['native_file_tools_verified']=True
manifest['hermes']['existing_shell_override']=r'HERMES_GIT_BASH_PATH=D:\Git\bin\bash.exe (process only)'
save_json(ROOT/'installation-manifest.json',manifest)
print(json.dumps({'files_scanned':len(paths),'db_unchanged':True,'hermes_python_packages':len(packages)}))
