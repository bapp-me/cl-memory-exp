import base64
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from prepare import ROOT, read


def broker(value):
    cfg = read(ROOT / '.local/native-broker.json')
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
