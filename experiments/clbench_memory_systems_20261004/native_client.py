import base64
import json
import hashlib
import shutil
import io
import tarfile
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from prepare import ROOT, read
BROKER_KIND='default'


def freeze_runtime():
    files={p.name:p.read_bytes() for p in (ROOT/'native-runtime').glob('*.py')}
    inventory={name:hashlib.sha256(data).hexdigest() for name,data in sorted(files.items())}
    fingerprint=hashlib.sha256(json.dumps(inventory,sort_keys=True).encode()).hexdigest()
    directory=ROOT/'.local/native-runtime-builds'/fingerprint
    if directory.exists():
        if any(hashlib.sha256((directory/name).read_bytes()).hexdigest()!=value for name,value in inventory.items()):
            raise RuntimeError('Immutable native runtime snapshot changed')
    else:
        directory.mkdir(parents=True)
        for name,data in files.items(): (directory/name).write_bytes(data)
    return fingerprint


def broker(value):
    suffix='' if BROKER_KIND=='default' else '-codex'
    cfg = read(ROOT / f'.local/native-broker{suffix}.json')
    req = Request(cfg['url'], data=json.dumps(value).encode(),
                  headers={'Content-Type': 'application/json', 'X-Broker-Token': cfg['token']})
    try:
        with urlopen(req, timeout=180) as response: return json.load(response)
    except HTTPError as exc:
        raise RuntimeError(exc.read().decode()) from exc


def put(container, path, value):
    return broker({'op': 'put', 'container_id': container, 'path': path,
                   'data': base64.b64encode(json.dumps(value).encode()).decode()})


def snapshot(container, path):
    result = broker({'op': 'snapshot', 'container_id': container})
    path.write_bytes(base64.b64decode(result['data']))


def restore(container,path):
    # Existing /state roots are broker-owned. Preserve regular files, while
    # allowing tar to create child directories without changing root metadata.
    content=io.BytesIO()
    with tarfile.open(path) as source,tarfile.open(fileobj=content,mode='w:gz') as target:
        for member in source.getmembers():
            if member.isdir():continue
            if not member.isfile():raise ValueError('Unsupported native state link')
            target.addfile(member,source.extractfile(member))
    payload=content.getvalue()
    receipt=broker({'op':'restore','container_id':container,'data':base64.b64encode(payload).decode()})
    if receipt['archive_sha256']!=hashlib.sha256(payload).hexdigest():
        raise RuntimeError('Transferred native state archive hash mismatch')
    return receipt
