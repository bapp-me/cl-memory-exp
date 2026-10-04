"""Concurrent real-container control test; deliberately no model-capable branch."""
from concurrent.futures import ThreadPoolExecutor
import time
from native_client import broker,put
from prepare import ROOT,save

created=[]; jobs=[]
try:
    with ThreadPoolExecutor(max_workers=4) as pool:
        created=list(pool.map(lambda _:broker({'op':'create'}),range(4)))
    for item in created:
        c=item['container_id']
        put(c,'/state/tasks/fixture/input.json',{'framework':'unsupported_fixture_only','project_key':'fixture'})
        jobs.append((c,broker({'op':'launch','container_id':c,'task':'fixture'})['job_id']))
    def poll(pair):
        c,job=pair
        return broker({'op':'poll','container_id':c,'job_id':job})
    with ThreadPoolExecutor(max_workers=8) as pool:
        checks=list(pool.map(poll,jobs*25))
    deadline=time.monotonic()+20
    while any(poll(j)['running'] for j in jobs):
        if time.monotonic()>deadline: raise TimeoutError('Fixture subprocess did not exit')
        time.sleep(.1)
    assert all(poll(j)['exit_code']==1 for j in jobs)
    save(ROOT/'records/native-broker-fixture.json',{'status':'passed','model_calls':0,
        'checks':['four simultaneous isolated container creations','100 concurrent job status reads',
                  'all no-model fixture subprocesses terminated with expected unsupported-mode result']})
    print('Native broker concurrency fixture passed; model_calls=0')
finally:
    for c in created:
        broker({'op':'remove','container_id':c['container_id']})
