thread_id: 01a10b0d-a435-77d3-ab98-0dc606f822bc
updated_at: 2026-10-05T08:02:09+00:00
rollout_path: /state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-53-25-01a10b0d-a435-77d3-ab98-0dc606f822bc.jsonl
cwd: /state/work/database

# clbench Q21: median list price of electronics with catalog images and positive list price — answered 21.99, CORRECT in 13/15 queries

Rollout context: SQLite benchmark question 21/40 in /state/work/database via CLBENCH_ACTION (15-query budget, 50-row result cap, exact-match grading). Prior memory playbook (MEMORY.md + skills/clbench-sql-benchmark/SKILL.md) was read first and supplied g2=electronics mapping, price-unit facts, and the even-safe median pattern.

## Task 1: Compute median list price (dollars) for electronics with at least one catalog image and positive list price

Outcome: success ("Question 21: CORRECT. Your answer: 21.99. Exploratory queries used: 13")

Preference signals:
- None from a human user; benchmark harness. Behaviorally relevant defaults: the run deliberately probed alternate price-column/population interpretations before spending the ANSWER, following the Q18 INCORRECT postmortem.

Key steps:
- Read MEMORY.md and skill first; confirmed g2=electronics and median CTE pattern.
- Dumped sqlite_master for g2 tables; PRAGMA table_info(items_g2) confirmed columns including `img_ct` and a new `prc_v2 INTEGER` column.
- Computed medians for all three candidate columns in one consolidated query (ROW_NUMBER + rn IN ((n+1)/2,(n+2)/2)): prc_usd→20.95 (6344 rows), prc_v2/100→22.09 (6568 rows), prc/100→21.99 (6568 rows).
- Checked prc_v2 semantics: not consistently higher than prc_usd (760 higher, 501 lower, 5083 equal cents) — not obviously "list price"; no 'List Price' text in feat_lst.
- NULL-overlap query on all 20,000 rows: prc_null=13430, prc_usd_null=13654, prc_v2_null=13430, prc_only=224, usd_only=0, prc=prc_usd*100 with 0 mismatches. prc and prc_v2 share the same NULL set; prc_usd has 224 fewer non-null rows.
- Corrected an initial median bug (MIN over middle rows instead of AVG for even n); true medians confirmed 21.99 (prc) vs 22.09 (prc_v2).
- Submitted ANSWER 21.99 (prc in cents / 100, filtered img_ct>0 AND prc>0, 6568 rows) → CORRECT.

Failures and how to do differently:
- `ERROR: no such column: img_ct` on the first consolidated CTE was self-inflicted: the CTE's SELECT list omitted img_ct while the outer query referenced it — not a schema problem. Include every referenced column in the CTE.
- `ERROR: You can only execute one statement at a time` — the CLBENCH_ACTION QUERY endpoint rejects multi-statement inputs (even `SELECT ...; PRAGMA ...`). Run one statement per query; each failed call still consumed budget.
- Initial median used MIN over the two middle rows, which happens to work only for certain values; correct even-n median is AVG of rows rn IN ((n+1)/2,(n+2)/2).
- Efficiency: 13/15 queries is high vs. prior 1–3 query solves; the ambiguity here (three price columns) justified extra probes, but several queries were wasted on failed multi-statement calls and a misread CTE error.

Reusable knowledge:
- CORRECT Q21 answer: 21.99 = median(items_g2.prc)/100 over rows WHERE img_ct>0 AND prc>0 (6568 rows). "List price" in dollars maps to `prc` (cents), NOT `prc_usd` (whose median would be 20.95 over 6344 rows) and NOT `prc_v2` (22.09, cents, semantics unclear — deviates from prc_usd*100 in both directions).
- This instance's items_g2 includes `img_ct INTEGER` and `prc_v2 INTEGER` beyond previously recorded schema. prc and prc_v2 have identical NULL sets (13,430 NULLs); prc_usd has 224 extra NULLs (13,654). prc = prc_usd*100 verified with 0 mismatches; prc_v2 ≠ prc_usd*100 for 1,261 rows (760 higher, 501 lower).
- CLBENCH_ACTION QUERY executes exactly one statement per call; multi-statement content fails with "ERROR: You can only execute one statement at a time" and still burns query budget.
- Self-check: "no such column" errors from a hand-written CTE may be a missing column in the CTE SELECT list, not the schema — verify with PRAGMA table_info before concluding the schema changed.
- Even-count median in SQLite: AVG of ROW_NUMBER rn IN ((n+1)/2,(n+2)/2), not MIN/MAX of the middle rows.

References:
- Winning answer query shape: `WITH p AS (SELECT prc, ROW_NUMBER() OVER (ORDER BY prc) r1, COUNT(*) OVER () n FROM items_g2 WHERE img_ct > 0 AND prc > 0) SELECT AVG(CASE WHEN r1 IN ((n+1)/2,(n+2)/2) THEN prc END)/100.0 FROM p;` → 21.99, n=6568.
- Column-comparison medians: prc_usd 20.95 (6344 rows), prc_v2/100 22.09 (6568), prc/100 21.99 (6568).
- Benchmark feedback: "Question 21: CORRECT. Your answer: 21.99. Exploratory queries used: 13"
- Prior postmortem consulted: rollout_summaries/2026-10-05T07-40-20-jdZq-clbench_q18_electronics_avg_listed_price_incorrect_52956.md (probe population/format before ANSWER).

