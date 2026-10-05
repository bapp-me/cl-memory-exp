# Raw Memories

Merged stage-1 raw memories (stable ascending thread-id order):

## Thread `01a10a82-e3f0-7cf3-8171-c1d42698ad61`
updated_at: 2026-10-05T05:23:34+00:00
cwd: /state/work/database
rollout_path: /state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-21-52-01a10a82-e3f0-7cf3-8171-c1d42698ad61.jsonl
rollout_summary_file: 2026-10-05T05-21-52-P0KB-clbench_office_reviews_2031_timestamp_count_incorrect.md

---
description: Benchmark SQL task counting office-product reviews dated >=2031 in anonymized g1/g2/g3 SQLite DB; agent answered 0 after ms/µs timestamp analysis and was marked INCORRECT.
task: count office-product (fdbk_g1) reviews with timestamps in year 2031 or later in benchmark SQLite DB
task_group: clbench-sql-benchmark
task_outcome: fail
cwd: /state/work/database
keywords: clbench, sqlite, fdbk_g1, items_g1, timestamp precision, unixepoch, millisecond, microsecond, sqlite_master, benchmark question, strftime
---

### Task 1: Count office-product reviews dated >= 2031

task: identify office-product review table via schema exploration, then count rows with ts year >= 2031
task_group: clbench-sql-benchmark
task_outcome: fail

Preference signals:
- No human preference evidence; harness constraints only: exact-value ANSWER, 15 exploratory QUERY budget, 50-row result cap.

Reusable knowledge:
- clbench product DB schema: three anonymized groups — g1 = office products (items_g1 main_cat 'Office Products', 13933 items), g2 = electronics, g3 = musical instruments. Review tables fdbk_g1/g2/g3 with ts column (INTEGER in g1/g2, TEXT in g3); supporting tables attrs_gN, taxn_gN, fdbk_stats_gN.
- `datetime(ts,'unixepoch')` returns NULL for millisecond/microsecond epoch integers — divide by 1000 or 1000000 first.
- fdbk_g1.ts has mixed precision: 13-digit ms rows (377,414 rows, dates 2001–2023 as ms) and 15-digit rows (58 rows, dated 1999–2001 under µs assumption — this assumption was unverified and may be wrong).
- Each QUERY tool call consumes exploratory budget; 6 of 15 were used in this failed attempt.

Failures and how to do differently:
- Submitted ANSWER `0` (count via `strftime('%Y', ts/1000,'unixepoch') >= 2031`); benchmark replied verbatim "Question 1: INCORRECT. Your answer: 0. Exploratory queries used: 6". The unit interpretation was therefore flawed somewhere despite the precision probe.
- Failure shield: before answering "count rows with date >= X" on unfamiliar epoch columns, compute a full per-year histogram under the chosen interpretation and test alternative units (s/ms/µs/ns) for plausibility; do not submit 0 based on a single interpretation. Apply the per-row CASE-on-length(ts) conversion in the final count, not just in min/max probes, and consider that short (58-row) minority-precision buckets may use a different epoch than assumed.

References:
- Schema query: `SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;`
- Precision probe: `SELECT length(ts) AS digits, COUNT(*), MIN(ts), MAX(ts) FROM fdbk_g1 GROUP BY length(ts)` → 13 digits: 377,414 rows (1001508857000..1694289928353); 15 digits: 58 rows (931911943000000..999499485000000).
- Failed count: `SELECT COUNT(*) FROM fdbk_g1 WHERE CAST(strftime('%Y', ts/1000, 'unixepoch') AS INTEGER) >= 2031;` → 0 (marked INCORRECT).

## Thread `01a10a87-c94a-7d71-bbdb-ce5c5e357ba7`
updated_at: 2026-10-05T05:27:53+00:00
cwd: /state/work/database
rollout_path: /state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-27-13-01a10a87-c94a-7d71-bbdb-ce5c5e357ba7.jsonl
rollout_summary_file: 2026-10-05T05-27-13-XSJx-sqlite_median_electronics_price_incorrect.md

---
description: SQL benchmark Q2 median electronics price answered 20.92 via items_g2.prc_usd — marked INCORRECT; table/category mapping was never verified and schema was guessed.
task: compute median non-zero price of electronics products in SQLite benchmark and submit via ANSWER
task_group: sql-benchmark
task_outcome: fail
cwd: /state/work/database
keywords: SQLite, median, ROW_NUMBER, items_g2, prc_usd, sqlite_master, CLBENCH_ACTION, clbench, electronics, schema exploration
---

### Task 1: Median price of non-zero electronics products (benchmark Q2)

task: median non-zero-price electronics products, rounded to 2 decimals, submitted as ANSWER
task_group: sql-benchmark
task_outcome: fail

Preference signals:
- None explicit from user; task came from benchmark harness instructions requiring schema exploration before answering and exact-value ANSWER submissions.

Reusable knowledge:
- Table `items_g2` schema (verified via sqlite_master): `ref_id TEXT PRIMARY KEY, ttl TEXT, avg_rtg REAL, prc INTEGER, prc_usd REAL, str_nm TEXT, main_cat TEXT, feat_lst TEXT, img_ct INTEGER`. Columns are abbreviated — never assume `price` exists.
- Median SQL pattern that ran successfully: CTE filtering non-null/non-zero prices, ROW_NUMBER() OVER (ORDER BY price), then `ROUND(AVG(price),2)` over `rn IN ((n+1)/2, (n+2)/2)`.
- Benchmark rules: 15 exploratory queries max, results capped at 50 rows, ANSWER must be the exact value; grader returns only INCORRECT/CORRECT with no diagnosis.

Failures and how to do differently:
- First query guessed a `price` column on `items_g2` → `ERROR: no such column: price`, wasting 1 of 15 queries. Check `PRAGMA table_info` / sqlite_master.sql before writing data queries.
- The agent assumed `items_g2` is the electronics table without verifying. The task states three category datasets with separate tables; future runs should first list tables and inspect category-discriminating columns (e.g. `main_cat`) or table-name patterns to map tables to categories, and apply a category filter if needed. The submitted 20.92 was marked INCORRECT, consistent with a wrong table/category or wrong price column choice (`prc` vs `prc_usd`).

References:
- Schema query: `SELECT sql FROM sqlite_master WHERE type='table' AND name='items_g2';`
- Submitted answer: `20.92`; grader response: `Question 2: INCORRECT. Your answer: 20.92. Exploratory queries used: 3`

## Thread `01a10a8d-e6fc-7e61-8a29-0d1ed3c89d5e`
updated_at: 2026-10-05T05:34:56+00:00
cwd: /state/work/database
rollout_path: /state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-33-54-01a10a8d-e6fc-7e61-8a29-0d1ed3c89d5e.jsonl
rollout_summary_file: 2026-10-05T05-33-54-sC2G-clbench_office_reviews_2022_price_20_200_count_incorrect.md

---
description: clbench Q3 office-product review count for 2022 with price strictly between $20 and $200; answered 8164 after 2 queries relying on stored mixed-epoch playbook, marked INCORRECT; failed to re-verify timestamp units/price column before submitting.
task: count fdbk_g1 reviews in calendar year 2022 for office products with items_g1.prc strictly between 20 and 200 (clbench SQLite benchmark)
task_group: clbench-sql-benchmark
task_outcome: fail
cwd: /state/work/database
keywords: clbench, sqlite, fdbk_g1, items_g1, prc, main_cat, timestamp precision, mixed epoch, length(ts), sqlite_master, benchmark question, INCORRECT, 8164, price boundaries, 2022
---

### Task 1: Count office-product reviews in 2022 with price strictly in (20, 200)

task: clbench exact-value count question
task_group: clbench-sql-benchmark
task_outcome: fail

Preference signals:
- The agent relied on the stored clbench playbook and submitted after only 2 of 15 queries without re-running the length(ts) histogram/year verification the playbook itself requires -> future runs should re-verify timestamp units and column semantics per question even when memory provides a schema playbook.

Reusable knowledge:
- Verified items_g1 schema: `ref_id TEXT PRIMARY KEY, ttl TEXT, avg_rtg REAL, avg_rtg_30d REAL, rtg_ct INTEGER, prc REAL, str_nm TEXT, main_cat TEXT, desc_txt TEXT, feat_lst TEXT` (g1 has no prc_usd; only items_g2 does).
- fdbk_g1 joins items_g1 on ref_id; ts is INTEGER with known mixed precision (13-digit ms rows; 15-digit rows).
- 2022 epoch bounds: 1640995200..1672531199.
- Answer 8164 for this question was graded INCORRECT — known-bad answer; suspect the unverified 15-digit/µs conversion, the boundary predicate, or the price column choice.

Failures and how to do differently:
- Submitted 8164 after trusting stored memory's mixed-epoch CASE (`LENGTH(ts)=13 -> /1000; =15 -> /1000000`) without verifying the per-length histogram or year distribution on this instance. Harness replied "Question 3: INCORRECT. Your answer: 8164. Exploratory queries used: 2" and the instance closed with no retry. Future runs: spend 1–2 queries on `SELECT LENGTH(ts), COUNT(*), MIN(ts), MAX(ts) FROM fdbk_g1 GROUP BY LENGTH(ts);` plus a year histogram before the final count; use more of the 15-query budget for verification.

References:
- Failing query shape: `SELECT COUNT(*) FROM fdbk_g1 f JOIN items_g1 i ON i.ref_id=f.ref_id WHERE i.main_cat='Office Products' AND i.prc>20 AND i.prc<200 AND CASE WHEN LENGTH(f.ts)=13 THEN f.ts/1000 WHEN LENGTH(f.ts)=15 THEN f.ts/1000000 ELSE f.ts END BETWEEN 1640995200 AND 1672531199` -> 8164 (graded INCORRECT).
- Schema discovery: `SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;`
- Stored playbook: /state/home/.codex/memories/MEMORY.md; /state/home/.codex/memories/skills/clbench-sql-benchmark/SKILL.md

