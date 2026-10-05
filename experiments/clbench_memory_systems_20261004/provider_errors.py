"""Classify structured provider errors, never text emitted by the agent."""
import json


def resource_error(raw):
    for line in raw.splitlines():
        line=line.removeprefix('data: ').strip()
        try:value=json.loads(line)
        except ValueError:continue
        if not isinstance(value,dict):continue
        response=value.get('response')
        errors=[value.get('error'),response.get('error') if isinstance(response,dict) else None]
        if value.get('type')=='error':errors.append(value)
        for error in errors:
            if isinstance(error,dict) and str(error.get('code')) in {'1113','insufficient_quota'}:
                return {'code':str(error['code']),'message':error.get('message','')}
    return None
