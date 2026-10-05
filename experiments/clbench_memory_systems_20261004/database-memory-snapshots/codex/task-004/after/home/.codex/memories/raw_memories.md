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

## Thread `01a10a9f-9035-7461-8016-764c7ccd0e4a`
updated_at: 2026-10-05T05:56:10+00:00
cwd: /state/work/database
rollout_path: /state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-53-11-01a10a9f-9035-7461-8016-764c7ccd0e4a.jsonl
rollout_summary_file: 2026-10-05T05-53-11-HquC-clbench_q4_electronics_price_reviews_rating_answer_8.md

---
description: clbench SQLite Q4 — counted electronics items >$50 with >=5 reviews and avg review rating <3.0; answer 8 CORRECT in 4 queries; key facts: g2 is electronics dataset despite no main_cat='Electronics', prc_usd is dollars and prc=prc_usd*100, rating source matters.
task: answer clbench SQLite benchmark question via CLBENCH_ACTION (aggregate filter query)
task_group: clbench-sql-benchmark
task_outcome: success
cwd: /state/work/database
keywords: clbench, CLBENCH_ACTION, sqlite_master, items_g2, fdbk_g2, prc_usd, main_cat, avg rating, review count, consolidated verification query
---

### Task 1: Count electronics products >$50 with >=5 reviews and avg review rating <3.0

task: clbench SQLite aggregate-count question answered via CLBENCH_ACTION QUERY/ANSWER
task_group: clbench-sql-benchmark
task_outcome: success

Reusable knowledge:
- g2 is the electronics dataset even though `main_cat='Electronics'` has 0 rows in items_g2; only 'All Electronics' (4562 items) and other '%Electronics%' labels exist. Category-to-group mapping must be verified by content aggregates, not exact label lookup (per skill SKILL.md step 3).
- items_g2 `prc` is cents: verified `ABS(prc_usd*100-prc)` mismatch count = 0 across both columns non-null. Use `prc_usd` for dollar-denominated questions; using `prc > 50` yields 26 vs correct 8.
- "average review rating" resolved to AVG(rtg) aggregated from fdbk_g2 per item (answer 8), not items.avg_rtg (which gives 3). When both exist, computing from feedback rows matched the grader.
- Efficient pattern that solved it in 4/15 queries: (1) schema dump from sqlite_master; (2) one UNION-ALL aggregate per group joining items to per-ref_id feedback COUNT/AVG grouped by main_cat with candidate-answer columns; (3) targeted narrowing probe on the candidate group; (4) semantic/unit verification (price columns, rating sources, null handling) in one wide query.
- Stored skill at /state/home/.codex/memories/skills/clbench-sql-benchmark/SKILL.md contains the full workflow, pitfalls (abbreviated columns prc/prc_usd/ttl/avg_rtg, mixed epoch units, category mapping), and verification checklist; loading it first is the established procedure.

Failures and how to do differently:
- None this run; no INCORRECT submissions. Failure shields that held: verifying prc/prc_usd semantics before answering and comparing both rating sources in one query avoided a wrong submission.

References:
- Winning predicate: `prc_usd>50 AND n>=5 AND ar<3` where `fb AS (SELECT ref_id, COUNT(*) n, AVG(rtg) ar FROM fdbk_g2 GROUP BY ref_id)` -> 8.
- Verification probe results: g2 null_prc_usd=13654, usd_p50=1613, raw_p50=6567, not_cents_ratio=0, ans_usd_fb=8, ans_usd_item=3, ans_raw_fb=26.
- Grader feedback verbatim: "Question 4: CORRECT. Your answer: 8. Exploratory queries used: 4".
- Skill path: /state/home/.codex/memories/skills/clbench-sql-benchmark/SKILL.md.

## Thread `01a10ab8-bdf2-7361-8e37-0dcc93c6535c`
updated_at: 2026-10-05T06:22:07+00:00
cwd: /state/work/database
rollout_path: /state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T06-20-41-01a10ab8-bdf2-7361-8e37-0dcc93c6535c.jsonl
rollout_summary_file: 2026-10-05T06-20-41-MFIw-clbench_q5_office_stored_vs_actual_rating_diff_over_1_correc.md

---
description: clbench Q5 solved in 2/15 queries — office products where stored avg_rtg differs from feedback-derived mean by >1 star = 2715 (CORRECT); direct predicate query beats diagnostic aggregate at float boundary.
task: count items where stored avg rating differs from actual mean review score by >1 star (clbench SQLite benchmark)
task_group: clbench-sql-benchmark
task_outcome: success
cwd: /state/work/database
keywords: clbench, sqlite, items_g1, fdbk_g1, avg_rtg, rtg, ref_id, ABS, boundary floating point, exact-value answer, 2715
---

### Task 1: Office products with |stored avg_rtg − actual mean| > 1 star

task: clbench Question 5 — count office products whose stored average rating differs from the mean of their review scores by more than 1 full star
task_group: clbench-sql-benchmark
task_outcome: success

Preference signals:
- (Inferred workflow) run grepped memory notes first and solved in 2/15 queries without schema exploration -> on similar clbench questions, consult existing memory/skill notes before spending query budget.

Reusable knowledge:
- Answer to the stored-vs-actual rating diff question (office products): 2715, graded CORRECT. Working query: `WITH actual AS (SELECT ref_id, AVG(rtg) AS actual_mean FROM fdbk_g1 WHERE rtg IS NOT NULL GROUP BY ref_id) SELECT COUNT(*) FROM items_g1 i JOIN actual a ON i.ref_id=a.ref_id WHERE i.avg_rtg IS NOT NULL AND ABS(i.avg_rtg-a.actual_mean)>1`.
- Failure shield: 333 rows sit within ±1e-6 of the 1-star boundary; a diagnostic aggregate with epsilon (`>1.000000001`) returned 2,711 vs the direct plain `>1` predicate's 2,715. For exact-count benchmark answers with thresholds, submit the count from the plain direct predicate query, not from a diagnostic aggregate with epsilon tweaks.
- `items_g1.avg_rtg` had no NULLs among joined rows; 19,999 office items have feedback rows; rating diffs span 0–4.

Failures and how to do differently:
- None this run; prior-run lessons (PRAGMA/abbreviated columns, feedback-derived AVG as rating source) were applied successfully.

References:
- Query 1 (diagnostic): CTE AVG(rtg) per ref_id from fdbk_g1 → diff_over_1=19999, strict_over_1(>1.000000001)=2711, near_boundary=333, null_stored=0, min=0.0, max=4.0.
- Query 2 (submitted): plain `ABS(i.avg_rtg-a.actual_mean)>1` → 2715; grader: "Question 5: CORRECT. Your answer: 2715. Exploratory queries used: 2".
- Memory sources: /state/home/.codex/memories/MEMORY.md, skills/clbench-sql-benchmark/SKILL.md.

