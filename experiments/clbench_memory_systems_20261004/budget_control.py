"""Authorize output growth only from unused, observed provider length stops."""
from native_evidence import usage_for


def authorize_growth(out, route, previous):
    current=int(route.get('output_limit',16384))
    if previous!=current or current>=131072: raise ValueError('Output limit changed or provider maximum reached')
    used=set(route.get('growth_evidence',[]))
    candidates=[]
    for attempt in usage_for(out):
        usage=attempt['usage'] or {}
        output=usage.get('completion_tokens',usage.get('output_tokens',0))
        if attempt['attempt_id'] not in used and attempt['phase']=='finished' and attempt['http_status']==200 and (
            attempt['finish_reason'] in {'length','max_tokens'} and output>=current):
            candidates.append(attempt)
    if not candidates: raise ValueError('No unused output-budget exhaustion evidence')
    evidence=candidates[-1]['attempt_id']; updated=min(current*2,131072)
    return {**route,'output_limit':updated,'growth_evidence':[*used,evidence]}, {
        'previous_limit':current,'output_limit':updated,'context_window':262144,
        'compression_threshold':262144-updated,'evidence_attempt_id':evidence}
