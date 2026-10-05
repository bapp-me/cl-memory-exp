"""Small MCP stdio bridge to the same official CL-Bench action controller."""
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen

CFG = json.loads(open(sys.argv[1]).read())
DATABASE = CFG.get('environment', 'database_exploration') == 'database_exploration'
SCHEMA = ({'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['QUERY', 'ANSWER']},
            'content': {'type': 'string'}}, 'required': ['action', 'content'], 'additionalProperties': False}
          if DATABASE else {'type': 'object', 'properties': {'command': {'type': 'string'}, 'thought': {'type': 'string'}},
                            'required': ['command'], 'additionalProperties': False})


def action(arguments, call_id):
    return dispatch({'action': arguments, 'toolCallId': str(call_id)})


def final_action(text, call_id):
    # The locked official parser runs in the controller, never guessed commands.
    return dispatch({'control': 'final_response', 'text': text, 'toolCallId': str(call_id)})


def dispatch(value):
    request = Request(CFG['gateway'] + '/tool', data=json.dumps(value).encode(),
        headers={'Authorization': 'Bearer ' + CFG['gateway_token'], 'Content-Type': 'application/json'})
    with urlopen(request, timeout=600) as response: observed=json.load(response)
    path=Path(sys.argv[1]).parent/'last-business-result.json'
    temp=path.with_suffix('.tmp'); temp.write_text(json.dumps(observed)); temp.replace(path)
    return observed


def main():
    for line in sys.stdin:
        v = json.loads(line)
        if 'id' not in v: continue
        try:
            method = v['method']
            if method == 'initialize':
                result = {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}},
                          'serverInfo': {'name': 'clbench-business', 'version': '1'}}
            elif method == 'ping': result = {}
            elif method == 'tools/list':
                result = {'tools': [{'name': 'CLBENCH_ACTION', 'description': CFG['tool_description'], 'inputSchema': SCHEMA}]}
            elif method == 'tools/call':
                if v['params']['name'] != 'CLBENCH_ACTION': raise ValueError('Unknown tool')
                observed = action(v['params']['arguments'], v['id'])
                result = {'content': [{'type': 'text', 'text': json.dumps(observed)}], 'isError': False}
            else: raise ValueError('Unsupported method')
            reply = {'jsonrpc': '2.0', 'id': v['id'], 'result': result}
        except Exception as exc:
            # A controller failure must stop the framework through the supervisor,
            # not silently consume subsequent business actions as model mistakes.
            reply = {'jsonrpc': '2.0', 'id': v['id'], 'error': {'code': -32603, 'message': type(exc).__name__}}
        print(json.dumps(reply), flush=True)


if __name__ == '__main__': main()
