"""Transport-only substitute for the official modules' Docker subprocess calls."""
from __future__ import annotations
import base64
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from urllib.request import Request, urlopen
from prepare import ROOT, read


def broker(value):
    endpoint = read(ROOT / '.local/docker-broker.json')
    request = Request(endpoint['url'], data=json.dumps(value).encode(),
        headers={'Content-Type': 'application/json', 'X-Broker-Token': endpoint['token']})
    with urlopen(request, timeout=value.get('timeout', 120) + 30) as response:
        return json.load(response)


def run(argv, **kwargs):
    if not isinstance(argv, list) or argv[0] != 'docker':
        raise ValueError('Only explicit Docker argument arrays are admitted')
    timeout = kwargs.get('timeout') or 120
    if argv[1] == 'run':
        image = argv[argv.index('sleep') - 1]
        images = read(ROOT / 'records/docker-images.json')['images']
        if image.endswith(':tablib'): image = images['tablib']
        elif image.endswith(':tenacity'): image = images['tenacity']
        result = broker({'op': 'create', 'image': image, 'cwd': argv[argv.index('-w') + 1], 'timeout': timeout})
    elif argv[1] == 'exec':
        if '-e' in argv: raise ValueError('Unexpected environment forwarding')
        cwd = argv[argv.index('-w') + 1] if '-w' in argv else '/testbed'
        interpreter = next(i for i, part in enumerate(argv) if part in {'bash', 'sh', '/bin/bash', '/bin/sh'})
        if argv[interpreter + 1] != '-lc': raise ValueError('Unexpected interpreter shape')
        result = broker({'op': 'exec', 'container_id': argv[interpreter - 1], 'cwd': cwd,
                         'command': argv[interpreter + 2], 'timeout': timeout})
    elif argv[1] == 'cp':
        container, target = argv[3].split(':', 1)
        source = Path(argv[2]).resolve()
        if not source.is_relative_to(ROOT.resolve()): raise ValueError('Patch must be experiment-private')
        data = source.read_bytes()
        # Upstream writes a text NamedTemporaryFile. Undo only Windows' newline
        # translation before shipping it to Linux, restoring the original patch bytes.
        if target.startswith('/tmp/clbench_patch_'):
            data = data.replace(b'\r\n', b'\n')
        result = broker({'op': 'put', 'container_id': container, 'path': target,
                         'data': base64.b64encode(data).decode(), 'timeout': timeout})
    elif argv[1:3] == ['rm', '-f']:
        result = broker({'op': 'remove', 'container_id': argv[3], 'timeout': timeout})
    else: raise ValueError('Unexpected Docker operation')
    stdout, stderr = result.get('stdout', ''), result.get('stderr', '')
    if kwargs.get('stderr') == subprocess.STDOUT: stdout, stderr = stdout + stderr, ''
    completed = subprocess.CompletedProcess(argv, result['returncode'], stdout, stderr)
    if kwargs.get('check') and completed.returncode:
        raise subprocess.CalledProcessError(completed.returncode, argv, output=stdout, stderr=stderr)
    return completed


def install():
    from src.tasks.codebase_adaptation import generic_runtime
    from minisweagent.environments import docker
    # Substitute module bindings, not the process-global subprocess module.
    surface = SimpleNamespace(**{name: getattr(subprocess, name) for name in
        ['PIPE', 'STDOUT', 'DEVNULL', 'TimeoutExpired', 'CalledProcessError', 'CompletedProcess']}, run=run)
    generic_runtime.subprocess = surface
    docker.subprocess = surface
    def cleanup(self):
        if getattr(self, 'container_id', None):
            broker({'op': 'remove', 'container_id': self.container_id, 'timeout': 60})
            self.container_id = None
    docker.DockerEnvironment.cleanup = cleanup
