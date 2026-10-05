# Task Group: clbench SQL benchmark
scope: SQLite benchmark questions in /state/work/database, especially timestamp filtering over anonymized product-feedback tables; use before schema discovery or epoch-date counting.
applies_to: cwd=/state/work/database; reuse_rule=Safe for this clbench product-reviews benchmark and analogous SQLite epoch-timestamp questions; verify schema names and units before transferring exact table names to another checkout.

## Task 1: Count office-product reviews dated >= 2031

### rollout_summary_files

- rollout_summaries/2026-10-05T05-21-52-P0KB-clbench_office_reviews_2031_timestamp_count_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-21-52-01a10a82-e3f0-7cf3-8171-c1d42698ad61.jsonl, updated_at=2026-10-05T05:23:34+00:00, thread_id=01a10a82-e3f0-7cf3-8171-c1d42698ad61, status=fail, usefulness=high)

### keywords

- clbench, sqlite, fdbk_g1, items_g1, timestamp precision, unixepoch, millisecond, microsecond, sqlite_master, benchmark question, strftime, year 2031, mixed precision

## Reusable knowledge

- clbench product DB schema: three anonymized groups — g1 = office products (`items_g1.main_cat = 'Office Products'`, 13,933 items), g2 = electronics, g3 = musical instruments. Review tables are `fdbk_g1/g2/g3`; supporting tables are `attrs_gN`, `taxn_gN`, and `fdbk_stats_gN`. [Task 1]
- In the benchmark DB, `fdbk_g1.ts` is INTEGER and has mixed precision: 13-digit rows (377,414 rows; dates 2001–2023 when interpreted as milliseconds) and 15-digit rows (58 rows; dated 1999–2001 when interpreted as microseconds, an unverified assumption). `fdbk_g2.ts` is INTEGER and `fdbk_g3.ts` is TEXT. [Task 1]
- `datetime(ts,'unixepoch')` returns NULL for large millisecond/microsecond epoch integers; divide by the appropriate power of 1,000 before conversion. [Task 1]
- Start unfamiliar-schema discovery with `SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;`; identify product groups through `main_cat`, then inspect `length(ts)` distributions with `COUNT`, `MIN`, and `MAX`. [Task 1]
- Benchmark harness rules: submit an exact-value ANSWER, a 15-query cap applies to exploratory QUERY calls, each QUERY call consumes budget, and results are capped at 50 rows. The failed attempt used 6 queries. [Task 1]

## Failures and how to do differently

- Symptom: submitted `0` and benchmark replied "Question 1: INCORRECT. Your answer: 0. Exploratory queries used: 6." Cause: the epoch-unit interpretation was flawed somewhere despite min/max probes. Fix: before answering "count rows with date >= X" on an unfamiliar epoch column, compute a full per-year histogram under the chosen interpretation and test s/ms/µs/ns for domain plausibility. [Task 1]
- Do not submit 0 from a single-unit interpretation. Apply a per-row `CASE` on `length(ts)` in the final count, not merely in min/max probes, and consider that the short 58-row minority-precision bucket may use a different epoch than assumed. [Task 1]
- Precise per-row shape to adapt: convert each bucket by `length(ts)`, verify the resulting date-range and year-count distribution, and only then apply the `>= 2031` predicate. Avoid a uniform `strftime('%Y', ts/1000, 'unixepoch')` conversion when mixed lengths are present. [Task 1]
