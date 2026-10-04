import json
import time
from urllib.error import HTTPError
from urllib.request import Request,urlopen


def grow(cfg,previous):
    # The gateway writes its final usage receipt just after the SSE connection
    # closes; a short read-after-write wait does not issue another model call.
    for attempt in range(20):
        request=Request(cfg['gateway']+'/budget',data=json.dumps({'previous_limit':previous}).encode(),
            headers={'Authorization':'Bearer '+cfg['gateway_token'],'Content-Type':'application/json'})
        try:
            with urlopen(request,timeout=15) as response: return json.load(response)
        except HTTPError as exc:
            if exc.code!=409 or attempt==19: raise
            time.sleep(.1)
