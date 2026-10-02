"""Pre-specified expansion and baselines; execution is a separate explicit command."""
import argparse
import json
from pathlib import Path
from make_tasks import CATALOG

ROOT = Path(__file__).resolve().parent
GROUPS = [r[0] for r in CATALOG]
CAL = {'01_units', '04_pagination', '08_csv'}


def aid(g):
    return f'cal-pi-{g[:2]}-a' if g in CAL else f'main-pi-{g[:2]}-a'


def wid(g, guided=False):
    return ('guided-pi-' if guided else 'main-pi-') + g[:2] + '-w' if guided or g != '01_units' else 'cal-pi-01-w'


def job(g, stage, condition, agent='pi', prefix='main'):
    j = {'run_id': f'{prefix}-{agent}-{g[:2]}-{stage}-{condition}', 'group': g, 'stage': stage, 'agent': agent,
         'memory': 'none' if condition == 'none' else 'search' if condition == 'search' else 'file'}
    if condition != 'none':
        j['memory_from'] = wid(g, condition == 'guided')
    if condition == 'caution':
        j['caution'] = True
    return j


def jobs(phase):
    if phase == 'sources':
        return [{'run_id': aid(g), 'group': g, 'stage': 'a'} for g in GROUPS if g not in CAL]
    if phase in ('writers', 'guided_writers'):
        guided = phase == 'guided_writers'
        return [{'run_id': wid(g, guided), 'group': g, 'stage': 'a', 'writer_from': aid(g), 'guided': guided} for g in GROUPS if guided or g != '01_units']
    if phase in ('cal_consumers', 'main'):
        groups = [g for g in GROUPS if (g in CAL) == (phase == 'cal_consumers')]
        return [job(g, s, c) for idx, g in enumerate(groups) for s in 'bc' for c in (['none', 'file'] if idx % 2 == 0 else ['file', 'none'])]
    if phase in ('guided', 'caution', 'search'):
        return [job(g, s, phase) for g in GROUPS for s in 'bc']
    if phase == 'cross_agent':
        return [job(g, s, c, 'hermes', 'cross') for g in ('03_join', '04_pagination', '08_csv') for s in 'bc' for c in ('none', 'file', 'search')]
    if phase == 'cal_cross':
        return [job('01_units', 'b', 'none', 'hermes', 'cal2')]
    if phase == 'fix_followup':
        rows = []
        for idx, g in enumerate(GROUPS):
            frozen = {'run_id': f'fix-pi-{g[:2]}-d-frozen', 'group': g, 'stage': 'd', 'memory_from': wid(g)}
            updated = {'run_id': f'fix-pi-{g[:2]}-d-natural', 'group': g, 'stage': 'd', 'memory_from': f'main-pi-{g[:2]}-c-file'}
            retain = {'run_id': f'fix-pi-{g[:2]}-b-natural', 'group': g, 'stage': 'b', 'memory_from': f'main-pi-{g[:2]}-c-file'}
            rows += [frozen, updated, retain] if idx % 2 == 0 else [updated, frozen, retain]
        return rows
    if phase == 'explicit_repair':
        return [{'run_id': f'fix-pi-{g[:2]}-repair', 'group': g, 'stage': 'c', 'repair_from': f'main-pi-{g[:2]}-c-file'} for g in ('04_pagination', '05_update', '08_csv')]
    if phase == 'explicit_followup':
        return [{'run_id': f'fix-pi-{g[:2]}-{s}-explicit', 'group': g, 'stage': s, 'memory_from': f'fix-pi-{g[:2]}-repair'} for g in ('04_pagination', '05_update', '08_csv') for s in 'db']
    if phase == 'consumer_repeats':
        rows = []
        for repeat in (2, 3):
            for idx, g in enumerate(('02_coverage', '04_pagination', '06_build', '08_csv')):
                for s in 'bc':
                    for c in (('file', 'none') if (idx + repeat) % 2 else ('none', 'file')):
                        rows.append(job(g, s, c, prefix=f'repeat{repeat}'))
                    if g in ('06_build', '08_csv'):
                        for c in ('guided', 'caution'):
                            rows.append(job(g, s, c, prefix=f'repeat{repeat}'))
        return rows
    if phase == 'writer_repeats_a':
        return [{'run_id': f'writer2-pi-{g[:2]}-a', 'group': g, 'stage': 'a'} for g in ('02_coverage', '08_csv')]
    if phase == 'writer_repeats_w':
        return [{'run_id': f'writer2-pi-{g[:2]}-w', 'group': g, 'stage': 'a', 'writer_from': f'writer2-pi-{g[:2]}-a'} for g in ('02_coverage', '08_csv')]
    if phase == 'writer_repeats_consume':
        return [{'run_id': f'writer2-pi-{g[:2]}-{s}-file', 'group': g, 'stage': s, 'memory_from': f'writer2-pi-{g[:2]}-w'} for g in ('02_coverage', '08_csv') for s in 'bc']
    if phase == 'second_model':
        rows = []
        for g in ('02_coverage', '08_csv'):
            for s in 'bc':
                for c in ('none', 'file', 'guided'):
                    j = job(g, s, c, prefix='glm')
                    j['provider'] = 'glm'
                    rows.append(j)
        return rows
    if phase == 'glm_native':
        rows = []
        for g, stage, conditions in [('02_coverage', 'b', ('none', 'file')), ('02_coverage', 'c', ('none', 'file', 'guided')), ('08_csv', 'c', ('none', 'file', 'guided'))]:
            for c in conditions:
                j = job(g, stage, c, prefix='glmnative2')
                j.update(provider='glm', transport='native')
                rows.append(j)
        return rows
    if phase == 'ensure_read':
        return [dict(job(g, 'c', 'search', prefix='ensure'), ensure_read=True) for g in ('04_pagination', '05_update', '08_csv')]
    if phase == 'repair_retrieval':
        rows = []
        for g in ('04_pagination', '08_csv'):
            for condition, source in [('frozen', wid(g)), ('natural', f'main-pi-{g[:2]}-c-file'), ('explicit', f'fix-pi-{g[:2]}-repair')]:
                rows.append({'run_id': f'readfix-pi-{g[:2]}-d-{condition}', 'group': g, 'stage': 'd', 'memory': 'search', 'require_retrieval': True, 'memory_from': source})
        return rows
    if phase == 'natural_only':
        return [{'run_id': f'natural-pi-08-{s}-file', 'group': '08_csv', 'stage': s, 'memory_from': 'cal-pi-08-a'} for s in 'bc']
    if phase == 'hermes_repeats':
        return [job(g, 'c', 'file', 'hermes', f'repeat{r}') for r in (2, 3) for g in ('04_pagination', '08_csv')]
    if phase == 'hermes_repair':
        return [{'run_id': f'fix-hermes-{g[:2]}-repair', 'group': g, 'stage': 'c', 'agent': 'hermes', 'repair_from': f'cross-hermes-{g[:2]}-c-file'} for g in ('04_pagination', '08_csv')]
    if phase == 'hermes_fix_followup':
        rows = []
        for g in ('04_pagination', '08_csv'):
            for condition, source in [('frozen', wid(g)), ('natural', f'cross-hermes-{g[:2]}-c-file'), ('explicit', f'fix-hermes-{g[:2]}-repair')]:
                rows.append({'run_id': f'fix-hermes-{g[:2]}-d-{condition}', 'group': g, 'stage': 'd', 'agent': 'hermes', 'memory_from': source})
            rows.append({'run_id': f'fix-hermes-{g[:2]}-b-explicit', 'group': g, 'stage': 'b', 'agent': 'hermes', 'memory_from': f'fix-hermes-{g[:2]}-repair'})
        return rows
    if phase == 'fix_repeats':
        return [{'run_id': f'fix{r}-pi-{g[:2]}-d-{c}', 'group': g, 'stage': 'd', 'memory_from': source}
                for r in (2, 3) for g in ('04_pagination', '08_csv')
                for c, source in [('frozen', wid(g)), ('natural', f'main-pi-{g[:2]}-c-file'), ('explicit', f'fix-pi-{g[:2]}-repair')]]
    raise ValueError(phase)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('phase')
    a = p.parse_args()
    rows = jobs(a.phase)
    path = ROOT / 'jobs' / (a.phase + '.json')
    path.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
    print(f'{path.name}: {len(rows)} planned runs')
