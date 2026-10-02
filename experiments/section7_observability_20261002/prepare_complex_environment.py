"""Pin public embedding weights and dependency metadata; no language-model API."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import urllib.request
import shutil

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.runtime/complex-libs'))
os.environ['HF_HOME'] = str(ROOT / '.cache/hf')
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['USE_TF'] = '0'
os.environ['USE_FLAX'] = '0'


def main():
    from sentence_transformers import SentenceTransformer
    config = json.loads((ROOT / 'records/complex-confirmed-config-v1.json').read_text(encoding='utf-8'))
    model = config['mem0']['embedding']
    # Use verified regular files: Windows cannot create HF cache symlinks here.
    url = 'https://huggingface.co/api/models/' + model['model'] + '/revision/' + model['revision'] + '?blobs=true'
    with urllib.request.urlopen(url, timeout=45) as response:
        metadata = json.load(response)
    needed = {'config.json', 'sentence_bert_config.json', 'modules.json', 'config_sentence_transformers.json',
              'model.safetensors', 'tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json',
              'vocab.txt', '1_Pooling/config.json'}
    folder = ROOT / '.cache/embedding-model' / model['revision']
    folder.mkdir(parents=True, exist_ok=True)
    for item in metadata['siblings']:
        name = item['rfilename']
        if name not in needed:
            continue
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            download = 'https://huggingface.co/' + model['model'] + '/resolve/' + model['revision'] + '/' + name
            temporary = target.with_suffix(target.suffix + '.download')
            with urllib.request.urlopen(download, timeout=90) as response, temporary.open('wb') as stream:
                shutil.copyfileobj(response, stream)
            temporary.replace(target)
        raw = target.read_bytes()
        if item.get('lfs'):
            assert hashlib.sha256(raw).hexdigest() == item['lfs']['sha256'], name
        else:
            assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == item['blobId'], name
    path = str(folder)
    encoder = SentenceTransformer(path, device='cpu', trust_remote_code=False)
    assert encoder.max_seq_length == 256 and encoder.get_sentence_embedding_dimension() == 384
    vector = encoder.encode('local embedding acceptance', convert_to_numpy=True)
    assert len(vector) == 384
    files = [{'name': item.relative_to(path).as_posix(), 'sha256': hashlib.sha256(item.read_bytes()).hexdigest(),
              'bytes': item.stat().st_size} for item in sorted(Path(path).rglob('*')) if item.is_file()]
    packages = ['mem0ai', 'qdrant-client', 'portalocker', 'sentence-transformers', 'openai', 'protobuf',
                'torch', 'transformers', 'posthog', 'pydantic', 'httpx', 'huggingface-hub', 'scipy', 'numpy', 'sqlalchemy']
    versions = {name: importlib.metadata.version(name) for name in packages}
    report = {'model_calls': 0, 'language_model_calls': 0, 'local_embedding_fixture_calls': 1,
              'embedding_model': model['model'], 'revision': model['revision'], 'local_path': path,
              'dimensions': 384, 'max_seq_length': 256, 'device': 'cpu', 'weights': files, 'packages': versions}
    (ROOT / 'records/complex-environment.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'records/complex-requirements-lock.txt').write_text('\n'.join(f'{name}=={version}' for name, version in versions.items()) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'weights'}))


if __name__ == '__main__':
    main()
