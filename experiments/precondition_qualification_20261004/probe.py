#!/usr/bin/env python3
"""Offline falsification probe; synthetic, non-LLM, NOT a performance benchmark.

Python standard library only. All SQL executes in :memory:. No network, secrets,
subprocess, dynamic code execution, or persistent database mutations.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, asdict
from itertools import combinations, product
from pathlib import Path
import hashlib
import json
import random
import sqlite3
from typing import Callable

FEATURES = ('preserve_left', 'right_has_duplicates', 'matched_fanout', 'project_alpha')
SHAPES = ('unique', 'matched_duplicate', 'unmatched_duplicate', 'null_duplicate')

@dataclass(frozen=True)
class Case:
    case_id: str
    goal: str
    project: str
    left: list[dict]
    right: list[dict]
    shape: str  # Evaluator metadata, NEVER exported to model inputs.


def make_case(case_id: str, goal: str, shape: str, alpha: bool, seed: int) -> Case:
    rng = random.Random(seed)
    prefix = f'K{rng.randrange(10000, 99999)}_'
    ka, kb, ku = prefix + 'a', prefix + 'b', prefix + 'u'
    # Some affected records have zero amount: sums alone can hide duplication.
    av = 0 if seed % 3 == 0 else rng.randrange(10, 1000)
    left = [dict(rid=seed * 10 + 1, key=ka, amount=av),
            dict(rid=seed * 10 + 2, key=kb, amount=rng.randrange(10, 1000))]
    right = [dict(did=seed * 10 + 3, key=ka), dict(did=seed * 10 + 4, key=kb)]
    if shape == 'matched_duplicate':
        right.append(dict(did=seed * 10 + 5, key=ka))
    elif shape == 'unmatched_duplicate':
        right.extend([dict(did=seed * 10 + 5, key=ku), dict(did=seed * 10 + 6, key=ku)])
    elif shape == 'null_duplicate':
        right.extend([dict(did=seed * 10 + 5, key=None), dict(did=seed * 10 + 6, key=None)])
    elif shape != 'unique':
        raise ValueError(shape)
    rng.shuffle(left)
    rng.shuffle(right)
    return Case(case_id, goal, 'alpha' if alpha else 'beta', left, right, shape)


def execute_join(c: Case) -> list[tuple[int, int | None, int]]:
    con = sqlite3.connect(':memory:')
    try:
        con.execute('CREATE TABLE l (rid INTEGER PRIMARY KEY, k TEXT, amount INTEGER)')
        con.execute('CREATE TABLE r (did INTEGER PRIMARY KEY, k TEXT)')
        con.executemany('INSERT INTO l VALUES (?, ?, ?)', [(v['rid'], v['key'], v['amount']) for v in c.left])
        con.executemany('INSERT INTO r VALUES (?, ?)', [(v['did'], v['key']) for v in c.right])
        return con.execute('SELECT l.rid, r.did, l.amount FROM l LEFT JOIN r ON l.k = r.k ORDER BY l.rid, r.did').fetchall()
    finally:
        con.close()


def reference_pairs(c: Case) -> list[tuple[int, int | None, int]]:
    # Independent implementation of SQL equality/LEFT JOIN for this fixture.
    result = []
    for l in c.left:
        matches = [r for r in c.right if l['key'] is not None and r['key'] is not None and l['key'] == r['key']]
        if matches:
            result.extend((l['rid'], r['did'], l['amount']) for r in matches)
        else:
            result.append((l['rid'], None, l['amount']))
    return sorted(result, key=lambda row: (row[0], -1 if row[1] is None else row[1]))


def verifier(c: Case, rows: list[tuple[int, int | None, int]]) -> bool:
    """True = proposed operation satisfies the declared task grain.
    Test-based validity in this finite fixture, NOT formal semantic verification.
    """
    if c.goal == 'one_per_left':
        expected = Counter((l['rid'], l['amount']) for l in c.left)
        return Counter((rid, amount) for rid, _, amount in rows) == expected
    if c.goal == 'enumerate_pairs':
        return Counter(rows) == Counter(reference_pairs(c))
    raise ValueError('Unknown goal')


def features(c: Case) -> dict[str, bool]:
    # Hand-specified vocabulary is intentionally a strong SIMPLE control.
    counts = Counter(r['key'] for r in c.right)
    return dict(preserve_left=c.goal == 'one_per_left',
                right_has_duplicates=any(n > 1 for n in counts.values()),
                matched_fanout=any(l['key'] is not None and counts[l['key']] > 1 for l in c.left),
                project_alpha=c.project == 'alpha')


def public_case(c: Case) -> dict:
    instruction = ('保留左表粒度：每个左表 rid 在结果中恰好出现一次，amount 保持原值。'
                   if c.goal == 'one_per_left' else
                   '枚举左连接的所有匹配对；同一左表记录允许匹配多条右表记录。没有匹配时保留一条右侧为空的记录。')
    return dict(case_id=c.case_id, project=c.project, task=instruction,
                left_table=c.left, right_table=c.right,
                proposed_action='SELECT l.rid, r.did, l.amount FROM l LEFT JOIN r ON l.key = r.key',
                equality_note='按 SQLite 的等值 LEFT JOIN 语义；NULL 不与 NULL 匹配。')


def history_episode(c: Case) -> dict:
    rows = execute_join(c)
    ok = verifier(c, rows)
    return dict(input=public_case(c), observed_result=rows,
                visible_feedback=('输出符合本次要求。' if ok else '结果违反了本次的输出粒度要求；请核对每条左表记录的出现次数。'))


def hypotheses() -> list[tuple[tuple[str, bool], ...]]:
    # Learn a BLOCK rule from conjunctions. Empty conjunction = always block.
    # This is finite enumeration, not STAND and not a proposed novel algorithm.
    hs = []
    for length in range(len(FEATURES) + 1):
        for subset in combinations(FEATURES, length):
            hs.extend(tuple(zip(subset, signs)) for signs in product((False, True), repeat=length))
    return hs


def predicts_block(h: tuple, f: dict[str, bool]) -> bool:
    return all(f[k] == value for k, value in h)


def consistent(examples: list[Case]) -> list[tuple]:
    labelled = [(features(c), not verifier(c, execute_join(c))) for c in examples]
    return [h for h in hypotheses() if all(predicts_block(h, f) == y for f, y in labelled)]


def rule_text(h: tuple) -> str:
    return ' AND '.join(k if v else 'NOT ' + k for k, v in h) or 'TRUE'


def summarize(cases: list[Case], block: Callable[[Case], bool | None]) -> dict:
    result = dict(cases=len(cases), unsafe=0, safe=0, caught_unsafe=0,
                  missed_unsafe=0, false_blocks=0, allowed_safe=0, abstain=0)
    for c in cases:
        bad = not verifier(c, execute_join(c))
        result['unsafe' if bad else 'safe'] += 1
        pred = block(c)
        if pred is None:
            result['abstain'] += 1
        elif bad:
            result['caught_unsafe' if pred else 'missed_unsafe'] += 1
        else:
            result['false_blocks' if pred else 'allowed_safe'] += 1
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path(__file__).parent / 'outputs')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    training_specs = [
        ('one_per_left', 'matched_duplicate', True),
        ('one_per_left', 'unique', False),
        ('enumerate_pairs', 'matched_duplicate', True),
        ('one_per_left', 'unmatched_duplicate', True),
        ('one_per_left', 'matched_duplicate', False),
    ]
    train = [make_case(f'h{i}', *s, 11+i) for i, s in enumerate(training_specs)]
    cases = [make_case(f'q{i:03d}', goal, shape, alpha, 100+i)
             for i, (goal, shape, alpha, _) in enumerate(product(
                 ('one_per_left', 'enumerate_pairs'), SHAPES, (True, False), range(3)))]
    vs_initial, vs_final = consistent(train[:2]), consistent(train)
    assert vs_initial and vs_final
    learned = min(vs_final, key=lambda h: (len(h), rule_text(h)))

    def consensus(c: Case) -> bool | None:
        predictions = {predicts_block(h, features(c)) for h in vs_initial}
        return next(iter(predictions)) if len(predictions) == 1 else None

    policies = {
        'always_allow': lambda c: False,
        'always_block': lambda c: True,
        'right_unique_only': lambda c: features(c)['right_has_duplicates'],
        'unscoped_matched_fanout': lambda c: features(c)['matched_fanout'],
        'handwritten_task_aware_reference': lambda c: features(c)['preserve_left'] and features(c)['matched_fanout'],
        'enumerated_conjunction_from_5_examples': lambda c: predicts_block(learned, features(c)),
        'consensus_after_2_examples': consensus,
    }
    rows = {name: summarize(cases, policy) for name, policy in policies.items()}

    # Mutation validation: exact output checked independently, not only totals.
    checks = dict(sql_agrees_with_independent_join=0, exact_grain_detects_duplication=0,
                  legal_expansion_is_allowed=0, irrelevant_duplicates_are_allowed=0,
                  empty_output_is_rejected=0, corrupted_amount_is_rejected=0,
                  totals_only_false_negatives=0)
    for c in cases:
        output = execute_join(c)
        assert output == reference_pairs(c)
        checks['sql_agrees_with_independent_join'] += 1
        assert not verifier(c, [])
        checks['empty_output_is_rejected'] += 1
        mutated = [(rid, did, amount+1) for rid, did, amount in output]
        assert not verifier(c, mutated)
        checks['corrupted_amount_is_rejected'] += 1
        if c.goal == 'one_per_left' and features(c)['matched_fanout']:
            assert not verifier(c, output)
            checks['exact_grain_detects_duplication'] += 1
            if sum(r[2] for r in output) == sum(r['amount'] for r in c.left):
                checks['totals_only_false_negatives'] += 1
        if c.goal == 'enumerate_pairs':
            assert verifier(c, output)
            checks['legal_expansion_is_allowed'] += 1
        if c.shape in ('unmatched_duplicate', 'null_duplicate'):
            assert verifier(c, output)
            checks['irrelevant_duplicates_are_allowed'] += 1
    assert rows['handwritten_task_aware_reference']['missed_unsafe'] == 0
    assert rows['handwritten_task_aware_reference']['false_blocks'] == 0
    assert rows['enumerated_conjunction_from_5_examples']['missed_unsafe'] == 0
    assert rows['enumerated_conjunction_from_5_examples']['false_blocks'] == 0
    assert len(vs_initial) > len(vs_final)
    assert rows['consensus_after_2_examples']['abstain'] > 0
    assert checks['totals_only_false_negatives'] > 0

    report = dict(status='OFFLINE_SYNTHETIC_STRUCTURAL_CHECK_ONLY',
                  paid_model_calls=0, external_agent_runs=0,
                  training_examples=len(train), evaluation_instances=len(cases),
                  task_families=1, independent_real_world_incidents=0,
                  initial_consistent_hypotheses=len(vs_initial),
                  final_consistent_hypotheses=len(vs_final),
                  shortest_learned_block_rule=rule_text(learned),
                  checks=checks, policies=rows,
                  limitations=[
                      'The task goal and candidate feature vocabulary are hand-specified.',
                      'The author designed and inspected the generator and results; NOT a blind held-out benchmark.',
                      'No LLM rule synthesis, agent behavior, transfer to new mechanisms, or monetary savings was measured.',
                      'Complete current input is sufficient: this fixture does NOT establish that historical memory is necessary.',
                      'No method can identify a unique rule from observationally equivalent sparse evidence without assumptions or new evidence.',
                      'Zero errors here is neither formal verification nor a reliability guarantee.',
                  ])
    (args.out/'probe_results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (args.out/'history.json').write_text(json.dumps([history_episode(c) for c in train], ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (args.out/'public_cases.jsonl').write_text(''.join(json.dumps(public_case(c), ensure_ascii=False)+'\n' for c in cases), encoding='utf-8')
    (args.out/'evaluator_cases.jsonl').write_text(''.join(json.dumps(dict(case=asdict(c), should_block=not verifier(c, execute_join(c))), ensure_ascii=False)+'\n' for c in cases), encoding='utf-8')
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.out.iterdir()) if p.is_file() and p.name != 'sha256.json'}
    (args.out/'sha256.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
