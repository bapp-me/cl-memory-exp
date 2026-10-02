"""Download only public implementation metadata/source, never invoke a model."""
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'section7-source-audit'})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read()


def metadata(url):
    return json.loads(fetch(url))


def main():
    report = {'model_calls': 0, 'status': 'source_audit_only_no_complex_adapter_or_online_execution', 'sources': {}}
    package = metadata('https://pypi.org/pypi/mem0ai/0.1.118/json')
    wheel = next(item for item in package['urls'] if item['filename'].endswith('.whl'))
    raw = fetch(wheel['url'])
    assert hashlib.sha256(raw).hexdigest() == wheel['digests']['sha256']
    destination = ROOT / '.cache/complex-sources/mem0'
    destination.mkdir(parents=True, exist_ok=True)
    (destination / wheel['filename']).write_bytes(raw)
    entries = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = ['mem0/memory/main.py', 'mem0/configs/base.py', 'mem0/configs/llms/base.py',
                 'mem0/llms/openai.py', 'mem0/embeddings/huggingface.py', 'mem0/vector_stores/qdrant.py']
        for name in names:
            content = archive.read(name)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            entries.append({'path': name, 'sha256': hashlib.sha256(content).hexdigest()})
    report['sources']['mem0'] = {'package': 'mem0ai', 'version': '0.1.118', 'wheel_sha256': wheel['digests']['sha256'],
        'source_url': 'https://pypi.org/project/mem0ai/0.1.118/', 'files': entries,
        'selection_reason': 'Classic 0.1 vector-memory implementation for the planned paper-era baseline; current 2.x algorithm is a distinct setting'}
    for name, repository, paths in [
        ('awm', 'zorazrw/agent-workflow-memory', ['mind2web/pipeline.py', 'mind2web/online_induction.py', 'mind2web/utils/data.py', 'mind2web/prompt/instruction_action.txt']),
        ('ace', 'ace-agent/ace', ['ace/ace.py', 'ace/core/reflector.py', 'ace/core/curator.py',
                               'ace/prompts/reflector.py', 'ace/prompts/curator.py', 'playbook_utils.py'])]:
        commit = metadata('https://api.github.com/repos/' + repository + '/commits/main')
        revision = commit['sha']
        entries = []
        for path in paths:
            url = 'https://raw.githubusercontent.com/' + repository + '/' + revision + '/' + path
            content = fetch(url)
            target = ROOT / '.cache/complex-sources' / name / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            entries.append({'path': path, 'url': url, 'sha256': hashlib.sha256(content).hexdigest()})
        report['sources'][name] = {'repository': repository, 'revision': revision,
            'commit_time': commit['commit']['committer']['date'], 'files': entries}
    model_id = 'sentence-transformers/all-MiniLM-L6-v2'
    model = metadata('https://huggingface.co/api/models/' + model_id)
    revision = model['sha']
    entries = []
    for path in ['config.json', 'sentence_bert_config.json', 'modules.json', '1_Pooling/config.json']:
        url = 'https://huggingface.co/' + model_id + '/resolve/' + revision + '/' + path
        content = fetch(url)
        target = ROOT / '.cache/complex-sources/embedding' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        entries.append({'path': path, 'url': url, 'sha256': hashlib.sha256(content).hexdigest(), 'config': json.loads(content)})
    report['sources']['embedding'] = {'model': model_id, 'revision': revision, 'mode_proposed': 'local inference, no embedding API',
        'weights_downloaded': False, 'files': entries}
    target = ROOT / 'records/complex-source-audit.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'model_calls': 0, 'sources': {name: {k: v for k, v in value.items() if k in {'version', 'revision', 'model'}} for name, value in report['sources'].items()}}))


if __name__ == '__main__':
    main()
