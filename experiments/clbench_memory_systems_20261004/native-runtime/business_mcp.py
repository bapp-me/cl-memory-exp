"""Small MCP stdio bridge to the same official CL-Bench action controller."""
import json
import os
import sys
from urllib.request import Request, urlopen

CFG = json.loads(open(sys.argv[1]).read())
DATABASE = CFG.get('environment', 'database_exploration') == 'database_exploration'
SCHEMA = ({'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['QUERY', 'ANSWER']},
            'content': {'type': 'string'}}, 'required': ['action', 'content'], 'additionalProperties': False}
          if DATABASE else {'type': 'object', 'properties': {'command': {'type': 'string'}, 'thought': {'type': 'string'}},
                            'required': ['command'], 'additionalProperties': False})


def action(arguments, call_id):
    request = Request(CFG['gateway'] + '/tool', data=json.dumps({'action': arguments, 'toolCallId': str(call_id)}).encode(),
        headers={'Authorization': 'Bearer ' + CFG['gateway_token'], 'Content-Type': 'application/json'})
    with urlopen(request, timeout=600) as response: return json.load(response)


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
