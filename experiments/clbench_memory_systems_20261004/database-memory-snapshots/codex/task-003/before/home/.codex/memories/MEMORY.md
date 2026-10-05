# Task Group: clbench SQL benchmark
scope: SQLite benchmark questions in /state/work/database, including schema/category mapping, timestamp filtering, and median calculations over anonymized product-feedback tables; use before writing any data query.
applies_to: cwd=/state/work/database; reuse_rule=Safe for this clbench product-reviews benchmark and analogous SQLite schema/epoch/median questions; verify schema names, category mapping, and units before transferring exact table names to another checkout.

## Task 3: Count office-product reviews in 2022 with price strictly in (20, 200)

### rollout_summary_files

- rollout_summaries/2026-10-05T05-33-54-sC2G-clbench_office_reviews_2022_price_20_200_count_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-33-54-01a10a8d-e6fc-7e61-8a29-0d1ed3c89d5e.jsonl, updated_at=2026-10-05T05:34:56+00:00, thread_id=01a10a8d-e6fc-7e61-8a29-0d1ed3c89d5e, status=fail, usefulness=high)

### keywords

- clbench, sqlite, fdbk_g1, items_g1, prc, main_cat, timestamp precision, mixed epoch, length(ts), sqlite_master, benchmark question, INCORRECT, 8164, price boundaries, 2022

## Task 1: Count office-product reviews dated >= 2031

### rollout_summary_files

- rollout_summaries/2026-10-05T05-21-52-P0KB-clbench_office_reviews_2031_timestamp_count_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-21-52-01a10a82-e3f0-7cf3-8171-c1d42698ad61.jsonl, updated_at=2026-10-05T05:23:34+00:00, thread_id=01a10a82-e3f0-7cf3-8171-c1d42698ad61, status=fail, usefulness=high)

### keywords

- clbench, sqlite, fdbk_g1, items_g1, timestamp precision, unixepoch, millisecond, microsecond, sqlite_master, benchmark question, strftime, year 2031, mixed precision

## Task 2: Median price of non-zero electronics products

### rollout_summary_files

- rollout_summaries/2026-10-05T05-27-13-XSJx-sqlite_median_electronics_price_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-27-13-01a10a87-c94a-7d71-bbdb-ce5c5e357ba7.jsonl, updated_at=2026-10-05T05:27:53+00:00, thread_id=01a10a87-c94a-7d71-bbdb-ce5c5e357ba7, status=fail, usefulness=high)

### keywords

- clbench, sqlite, median, electronics, items_g2, prc_usd, prc, ROW_NUMBER, `ERROR: no such column: price`, sqlite_master, category mapping, main_cat, 20.92

## Reusable knowledge

- clbench product DB schema: three anonymized groups — g1 is office products (`items_g1.main_cat = 'Office Products'`, 13,933 items); g2 and g3 are described as electronics and musical instruments respectively. Review tables are `fdbk_g1/g2/g3`; supporting tables are `attrs_gN`, `taxn_gN`, and `fdbk_stats_gN`. The office mapping was verified, but the attempted electronics run never validated that its target was the correct table/category before answering. [Task 1][Task 2]
- In the benchmark DB, `fdbk_g1.ts` is INTEGER and has mixed precision: 13-digit rows (377,414 rows; dates 2001–2023 when interpreted as milliseconds) and 15-digit rows (58 rows; dated 1999–2001 when interpreted as microseconds, an unverified assumption). `fdbk_g2.ts` is INTEGER and `fdbk_g3.ts` is TEXT. [Task 1]
- `datetime(ts,'unixepoch')` returns NULL for large millisecond/microsecond epoch integers; divide by the appropriate power of 1,000 before conversion. [Task 1]
- Start unfamiliar-schema discovery with `SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;`; identify product groups through `main_cat`, then inspect `length(ts)` distributions with `COUNT`, `MIN`, and `MAX`. For item questions, map every table/category pair and inspect discriminating columns before calculating. [Task 1][Task 2]
- Verified `items_g2` schema: `ref_id TEXT PRIMARY KEY, ttl TEXT, avg_rtg REAL, prc INTEGER, prc_usd REAL, str_nm TEXT, main_cat TEXT, feat_lst TEXT, img_ct INTEGER`; column names are abbreviated and `price` does not exist. [Task 2]
- Verified `items_g1` schema: `ref_id TEXT PRIMARY KEY, ttl TEXT, avg_rtg REAL, avg_rtg_30d REAL, rtg_ct INTEGER, prc REAL, str_nm TEXT, main_cat TEXT, desc_txt TEXT, feat_lst TEXT`; g1 has no `prc_usd` — only `items_g2` does. `fdbk_g1` joins `items_g1` on `ref_id`. [Task 3]
- For calendar-year 2022, the epoch bounds are `1640995200..1672531199` (UTC). [Task 3]
- Known-bad result: the office-product 2022 count using `items_g1.prc > 20 AND prc < 200` and the mixed-epoch CASE returned `8164`; that exact answer was graded INCORRECT. [Task 3]
- For an odd/even-safe SQLite median, filter nulls and zeros as appropriate, use `ROW_NUMBER() OVER (ORDER BY price)`, count rows, then `ROUND(AVG(price),2)` over `rn IN ((n+1)/2, (n+2)/2)`. The pattern executed successfully; its specific 20.92 result was marked INCORRECT because the target/category selection was not verified. [Task 2]
- Benchmark harness rules: submit an exact-value ANSWER, a 15-query cap applies to exploratory QUERY calls, each QUERY call consumes budget, results are capped at 50 rows, and grading gives only INCORRECT/CORRECT without diagnosis. The timestamp attempt used 6 queries; the median attempt used 3. [Task 1][Task 2]
- Related skill: skills/clbench-sql-benchmark/SKILL.md

## Failures and how to do differently

- Symptom: submitted `0` and benchmark replied "Question 1: INCORRECT. Your answer: 0. Exploratory queries used: 6." Cause: the epoch-unit interpretation was flawed somewhere despite min/max probes. Fix: before answering "count rows with date >= X" on an unfamiliar epoch column, compute a full per-year histogram under the chosen interpretation and test s/ms/µs/ns for domain plausibility. [Task 1]
- Do not submit 0 from a single-unit interpretation. Apply a per-row `CASE` on `length(ts)` in the final count, not merely in min/max probes, and consider that the short 58-row minority-precision bucket may use a different epoch than assumed. [Task 1]
- Precise per-row shape to adapt: convert each bucket by `length(ts)`, verify the resulting date-range and year-count distribution, and only then apply the `>= 2031` predicate. Avoid a uniform `strftime('%Y', ts/1000, 'unixepoch')` conversion when mixed lengths are present. [Task 1]
- Symptom: `ERROR: no such column: price` wasted query 1/15. Cause: guessed an unabbreviated column on `items_g2`. Fix: run `PRAGMA table_info` or read `sqlite_master.sql` before the first data query; this benchmark uses `prc`, `prc_usd`, `ttl`, and `avg_rtg`. [Task 2]
- Symptom: submitted `20.92` and benchmark replied "Question 2: INCORRECT. Your answer: 20.92. Exploratory queries used: 3." Cause: the run computed from `items_g2.prc_usd` without verifying the electronics table/category mapping or choosing between `prc` and `prc_usd`. Fix: first list and inspect tables, confirm category discrimination through `main_cat` or related evidence, and identify the intended dollar column before spending budget on the final calculation. [Task 2]
- Symptom: submitted `8164` after only 2 of 15 queries and benchmark replied "Question 3: INCORRECT. Your answer: 8164. Exploratory queries used: 2." Cause: the run trusted the stored mixed-epoch CASE without running the required `length(ts)` histogram/year verification and did not independently re-test price-column semantics. Fix: reserve 1–2 queries for `SELECT LENGTH(ts), COUNT(*), MIN(ts), MAX(ts) FROM fdbk_g1 GROUP BY LENGTH(ts);` plus a year histogram, then re-verify the boundary predicate and price column before the final count. [Task 3]
