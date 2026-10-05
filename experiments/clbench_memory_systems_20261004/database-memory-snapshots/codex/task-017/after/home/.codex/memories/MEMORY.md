# Task Group: clbench SQL benchmark
scope: SQLite benchmark questions in /state/work/database, including schema/category mapping, supporting attribute/taxonomy tables, price units, review-rating sources, verified-review flags, body-length calculations, percentage/population semantics, float-sensitive numeric thresholds, timestamp filtering, and median calculations over anonymized product-feedback tables; use before writing any data query.
applies_to: cwd=/state/work/database; reuse_rule=Safe for this clbench product-reviews benchmark and analogous SQLite schema/epoch/median questions; verify schema names, category mapping, and units before transferring exact table names to another checkout.

## Task 1: Compute percentage of Computers & Accessories electronics above category-wide average price

### rollout_summary_files

- rollout_summaries/2026-10-05T06-38-05-VQ4J-clbench_q8_electronics_computers_accessories_pct_above_avg_p.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T06-38-05-01a10ac8-abff-7f21-87e2-efd65aa82d8d.jsonl, updated_at=2026-10-05T06:39:19+00:00, thread_id=01a10ac8-abff-7f21-87e2-efd65aa82d8d, status=fail, usefulness=high)

### keywords

- clbench, CLBENCH_ACTION, items_g2, taxn_g2, prc_usd, cat_lvl, cat_nm, main_cat, Computers & Accessories, category-wide average, percentage above average, INCORRECT, 24.44, sqlite_master, category mapping, top-level category

## Task 2: Compute average body-length difference for verified electronics 1-star versus 5-star reviews

### rollout_summary_files

- rollout_summaries/2026-10-05T06-32-13-sBIv-clbench_q7_verified_electronics_body_length_diff_answer_101.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T06-32-13-01a10ac3-4b11-72b1-89ee-329b2e346cbb.jsonl, updated_at=2026-10-05T06:33:26+00:00, thread_id=01a10ac3-4b11-72b1-89ee-329b2e346cbb, status=success, usefulness=high)

### keywords

- clbench, CLBENCH_ACTION, sqlite_master, fdbk_g2, items_g2, vrf, rtg, body, LENGTH, TRIM, verified, review body length, answer 101.8, 3 of 15 queries

## Task 3: Count distinct item_id minus distinct ref_id for office reviews rated <=2.0

### rollout_summary_files

- rollout_summaries/2026-10-05T06-27-20-GicW-clbench_q6_office_rtg_le_2_distinct_item_id_vs_ref_id_fk_cor.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T06-27-20-01a10abe-d341-78e3-8683-bfff91ec306a.jsonl, updated_at=2026-10-05T06:28:20+00:00, thread_id=01a10abe-d341-78e3-8683-bfff91ec306a, status=success, usefulness=high)

### keywords

- clbench, sqlite, fdbk_g1, items_g1, item_id, ref_id, foreign key, COUNT DISTINCT, rtg, exact-value answer, 1832, 2 of 15 queries

## Task 4: Count office products where stored avg_rtg differs from feedback-derived mean by >1 star

### rollout_summary_files

- rollout_summaries/2026-10-05T06-20-41-MFIw-clbench_q5_office_stored_vs_actual_rating_diff_over_1_correc.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T06-20-41-01a10ab8-bdf2-7361-8e37-0dcc93c6535c.jsonl, updated_at=2026-10-05T06:22:07+00:00, thread_id=01a10ab8-bdf2-7361-8e37-0dcc93c6535c, status=success, usefulness=high)

### keywords

- clbench, sqlite, items_g1, fdbk_g1, avg_rtg, rtg, ref_id, actual_mean, ABS, boundary floating point, exact-value answer, 2715, 2 of 15 queries

## Task 5: Count electronics products >$50 with >=5 reviews and avg review rating <3.0

### rollout_summary_files

- rollout_summaries/2026-10-05T05-53-11-HquC-clbench_q4_electronics_price_reviews_rating_answer_8.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-53-11-01a10a9f-9035-7461-8016-764c7ccd0e4a.jsonl, updated_at=2026-10-05T05:56:10+00:00, thread_id=01a10a9f-9035-7461-8016-764c7ccd0e4a, status=success, usefulness=high)

### keywords

- clbench, CLBENCH_ACTION, sqlite_master, items_g2, fdbk_g2, prc_usd, prc, main_cat, avg rating, review count, consolidated verification query, answer 8, 4 of 15 queries

## Task 6: Count office-product reviews in 2022 with price strictly in (20, 200)

### rollout_summary_files

- rollout_summaries/2026-10-05T05-33-54-sC2G-clbench_office_reviews_2022_price_20_200_count_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-33-54-01a10a8d-e6fc-7e61-8a29-0d1ed3c89d5e.jsonl, updated_at=2026-10-05T05:34:56+00:00, thread_id=01a10a8d-e6fc-7e61-8a29-0d1ed3c89d5e, status=fail, usefulness=high)

### keywords

- clbench, sqlite, fdbk_g1, items_g1, prc, main_cat, timestamp precision, mixed epoch, length(ts), sqlite_master, benchmark question, INCORRECT, 8164, price boundaries, 2022

## Task 7: Count office-product reviews dated >= 2031

### rollout_summary_files

- rollout_summaries/2026-10-05T05-21-52-P0KB-clbench_office_reviews_2031_timestamp_count_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-21-52-01a10a82-e3f0-7cf3-8171-c1d42698ad61.jsonl, updated_at=2026-10-05T05:23:34+00:00, thread_id=01a10a82-e3f0-7cf3-8171-c1d42698ad61, status=fail, usefulness=high)

### keywords

- clbench, sqlite, fdbk_g1, items_g1, timestamp precision, unixepoch, millisecond, microsecond, sqlite_master, benchmark question, strftime, year 2031, mixed precision

## Task 8: Median price of non-zero electronics products

### rollout_summary_files

- rollout_summaries/2026-10-05T05-27-13-XSJx-sqlite_median_electronics_price_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-27-13-01a10a87-c94a-7d71-bbdb-ce5c5e357ba7.jsonl, updated_at=2026-10-05T05:27:53+00:00, thread_id=01a10a87-c94a-7d71-bbdb-ce5c5e357ba7, status=fail, usefulness=high)

### keywords

- clbench, sqlite, median, electronics, items_g2, prc_usd, prc, ROW_NUMBER, `ERROR: no such column: price`, sqlite_master, category mapping, main_cat, 20.92

## Task 9: Count office products with reviews but absent from attributes

### rollout_summary_files

- rollout_summaries/2026-10-05T07-17-25-yGfc-clbench_q10_office_reviewed_not_in_attrs_count_correct_267.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-17-25-01a10aec-ae82-7191-a55c-d19c0a2e47f6.jsonl, updated_at=2026-10-05T07:18:06+00:00, thread_id=01a10aec-ae82-7191-a55c-d19c0a2e47f6, status=success, usefulness=high)

### keywords

- clbench, CLBENCH_ACTION, attrs_g1, fdbk_g1, ref_id, NOT EXISTS, reviewed but absent, not represented in attributes at all, unrepresented products, answer 267, 2 of 15 queries

## Task 10: Find year-month with most musical instrument reviews

### rollout_summary_files

- rollout_summaries/2026-10-05T06-53-17-hPnC-clbench_q9_musical_instruments_peak_month_2020_01_correct.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T06-53-17-01a10ad6-93c7-7a33-ae86-6c7a88c487ac.jsonl, updated_at=2026-10-05T06:55:31+00:00, thread_id=01a10ad6-93c7-7a33-ae86-6c7a88c487ac, status=success, usefulness=high)

### keywords

- clbench, CLBENCH_ACTION, fdbk_g3, items_g3, ref_id, Musical Instruments, main_cat, timestamp, epoch, strftime, ts is TEXT, 2020-01, ERROR: no such column: f.item_id, 5 of 15 queries

## Reusable knowledge

- `taxn_g2 (ref_id TEXT, cat_lvl INTEGER, cat_nm TEXT, FK→items_g2.ref_id)` is the taxonomy table; prior memories recorded `items_g2`/`fdbk_g2` but omitted `taxn_g2`. For `cat_nm='Computers & Accessories'`, `cat_lvl=1` has 8089 distinct `ref_id`s, 2447 with non-zero `prc_usd`, and `AVG(prc_usd)=54.925925623212095`. [Task 1]
- For Q8, 24.44 (598/2447 distinct non-zero `prc_usd` items above 54.93), computed via `taxn_g2.cat_lvl=1`, was marked INCORRECT. Before reusing that interpretation, probe all-non-zero-electronics average, non-DISTINCT populations, other `cat_lvl` values, zero-price handling, and `main_cat`-based selection. [Task 1]
- Known-good g2 facts re-confirmed: `items_g2` is electronics; `prc` is cents, `prc_usd` is dollars (`prc = prc_usd*100`); discover schema with `SELECT name, sql FROM sqlite_master WHERE type='table'`. [Task 1][Task 5]

- In `fdbk_g2`, `vrf` is TEXT and `vrf='true'` selects verified reviews. For the verified electronics body-length question, 1-star n=6634 averaged 286.3 characters and 5-star n=46717 averaged 184.5; the validated difference was `101.8`. [Task 2]
- For body-length questions, raw `LENGTH(body)` and `LENGTH(TRIM(body))` produced identical rounded averages in the Q7 instance (`whitespace_affected=0`); one consolidated query can compare both as a cheap hedge. [Task 2]
- The prior-memory-first workflow (`MEMORY.md` plus the skill) supplied the `g2=electronics` mapping/schema and answered Q7 in 3/15 queries, with only a targeted `fdbk_g2`/`items_g2` schema dump. [Task 2]
- Office attributes live in `attrs_g1 (ref_id TEXT, attr_key TEXT, attr_val TEXT)`, with `ref_id` as FK to `items_g1.ref_id`. "Not represented in attributes at all" maps to `NOT EXISTS (SELECT 1 FROM attrs_g1 a WHERE a.ref_id = f.ref_id)`; the exact-shape query returned 267 in 2/15 queries. [Task 9]
- `g3` is the musical instruments group: `items_g3` has 17,162 of 20,000 `main_cat='Musical Instruments'` (g1: 19; g2: 85). `fdbk_g3` contains cross-category rows (252,172 musical of 286,626 total), so filter through `items_g3` when wording restricts category; Q9's peak month was `2020-01` in both scopes. [Task 10]
- `fdbk_g3.ts` is TEXT; this instance's convertible values were all length-10 seconds with 3 unconvertible rows. Use the defensive multi-length CASE (already ISO string, then 10/13/16/19 digit epochs) and include the length histogram in one consolidated query. [Task 10]
- In `fdbk_g1`, the two product identifier columns are `item_id` (non-primary, TEXT) and `ref_id` (the declared FK to `items_g1.ref_id`). Verified from sqlite_master. [Task 3]
- For "how many more distinct values" questions, one consolidated query returning `COUNT(DISTINCT a) - COUNT(DISTINCT b)` plus both distinct counts can provide answer and sanity checks in one budgeted query; it solved Q6 in 2/15 queries. [Task 3]
- Consulting `MEMORY.md` and the skill first supplied office schema/rating-source rules and enabled a 2/15-query solve with no schema exploration. [Task 3][Task 4]

- For this benchmark instance, `items_g2` is the electronics dataset even though `main_cat='Electronics'` has 0 rows; only `All Electronics` (4,562 items) and other `%Electronics%` labels exist. Verify group/category mapping from content aggregates, never an exact label or table ordinal. [Task 5][Task 8]
- In `items_g2`, `prc` is cents and `prc_usd` is dollars; the relationship `prc = prc_usd * 100` was verified with 0 mismatches. For dollar-phrased questions, use `prc_usd` — `prc > 50` gave 26 versus the correct 8. [Task 5]
- When a question asks for "average review rating" and both sources exist, compute `AVG(rtg)` from the feedback rows per item: `fdbk_g2` gave answer 8, whereas `items.avg_rtg` gave 3; the feedback aggregate matched the grader. [Task 5]
- When the question explicitly contrasts the "stored average rating" with the "actual mean review score", use `items.avg_rtg` for stored and feedback-derived `AVG(rtg)` for actual; do not replace stored `avg_rtg` with feedback-derived AVG merely because both sources exist. [Task 4]
- Question 5, office products with `|items_g1.avg_rtg − feedback AVG(rtg)| > 1`, was CORRECT at `2715` with: `WITH actual AS (SELECT ref_id, AVG(rtg) AS actual_mean FROM fdbk_g1 WHERE rtg IS NOT NULL GROUP BY ref_id) SELECT COUNT(*) FROM items_g1 i JOIN actual a ON i.ref_id=a.ref_id WHERE i.avg_rtg IS NOT NULL AND ABS(i.avg_rtg-a.actual_mean)>1`. [Task 4]
- For exact-count threshold questions, submit the count from the plain, direct predicate (`ABS(diff)>1`). Diagnostic aggregation with epsilon `>1.000000001` returned 2,711 while the direct plain predicate returned the correct 2,715; 333 rows sit within ±1e-6 of the boundary. Use diagnostics to understand data, not as the submitted number. [Task 4]
- Efficient 4-query aggregate workflow: schema dump from `sqlite_master`; one UNION-ALL per group joining items to per-`ref_id` feedback `COUNT/AVG`, grouped by `main_cat`; targeted narrowing probe on the candidate group; then one wide semantic/unit verification covering price, rating, null handling, and candidate answers. [Task 5]
- clbench product DB schema: three anonymized groups — g1 is office products (`items_g1.main_cat = 'Office Products'`, 13,933 items); g2 and g3 are described as electronics and musical instruments respectively. Review tables are `fdbk_g1/g2/g3`; supporting tables are `attrs_gN`, `taxn_gN`, and `fdbk_stats_gN`. The office mapping was verified, but an attempted electronics run never validated that its target was the correct table/category before answering. [Task 7][Task 8]
- Verified `fdbk_g3(id INTEGER PK, ref_id TEXT FK->items_g3(ref_id), uid, rtg REAL, ttl, body, ts TEXT, hlp_ct INTEGER, vrf INTEGER)` and `items_g3(ref_id TEXT PK, ttl, avg_rtg REAL, rtg_ct INTEGER, prc REAL, str_nm, main_cat, desc_txt)`. Join feedback to items on `ref_id`, never `item_id`. [Task 10]
- In the benchmark DB, `fdbk_g1.ts` is INTEGER and has mixed precision: 13-digit rows (377,414 rows; dates 2001–2023 when interpreted as milliseconds) and 15-digit rows (58 rows; dated 1999–2001 when interpreted as microseconds, an unverified assumption). `fdbk_g2.ts` is INTEGER and `fdbk_g3.ts` is TEXT. [Task 7]
- `datetime(ts,'unixepoch')` returns NULL for large millisecond/microsecond epoch integers; divide by the appropriate power of 1,000 before conversion. [Task 7]
- Start unfamiliar-schema discovery with `SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;`; identify product groups through `main_cat`, then inspect `length(ts)` distributions with `COUNT`, `MIN`, and `MAX`. For item questions, map every table/category pair and inspect discriminating columns before calculating. [Task 7][Task 8]
- Verified `items_g2` schema: `ref_id TEXT PRIMARY KEY, ttl TEXT, avg_rtg REAL, prc INTEGER, prc_usd REAL, str_nm TEXT, main_cat TEXT, feat_lst TEXT, img_ct INTEGER`; column names are abbreviated and `price` does not exist. [Task 8]
- `items_g1.avg_rtg` had no NULLs among feedback-joined rows; 19,999 office items have feedback rows; stored-versus-actual rating diffs range 0–4 stars. [Task 4]
- Verified `items_g1` schema: `ref_id TEXT PRIMARY KEY, ttl TEXT, avg_rtg REAL, avg_rtg_30d REAL, rtg_ct INTEGER, prc REAL, str_nm TEXT, main_cat TEXT, desc_txt TEXT, feat_lst TEXT`; g1 has no `prc_usd` — only `items_g2` does. `fdbk_g1` joins `items_g1` on `ref_id`. [Task 4][Task 5]
- For calendar-year 2022, the epoch bounds are `1640995200..1672531199` (UTC). [Task 6]
- Known-bad result: the office-product 2022 count using `items_g1.prc > 20 AND prc < 200` and the mixed-epoch CASE returned `8164`; that exact answer was graded INCORRECT. [Task 6]
- For an odd/even-safe SQLite median, filter nulls and zeros as appropriate, use `ROW_NUMBER() OVER (ORDER BY price)`, count rows, then `ROUND(AVG(price),2)` over `rn IN ((n+1)/2, (n+2)/2)`. The pattern executed successfully; its specific 20.92 result was marked INCORRECT because the target/category selection was not verified. [Task 8]
- Benchmark harness rules: submit an exact-value ANSWER, a 15-query cap applies to exploratory QUERY calls, each QUERY call consumes budget, results are capped at 50 rows, and grading gives only INCORRECT/CORRECT without diagnosis. The timestamp attempt used 6 queries; the median attempt used 3. [Task 7][Task 8]
- Related skill: skills/clbench-sql-benchmark/SKILL.md

## Failures and how to do differently

- Q8 symptom: submitted 24.44 after 3 queries with no wide semantic verification, despite 12 queries remaining -> cause: skipped the skill's schema → aggregate → narrow → wide-verification shape at the interpretation step -> fix: for taxonomy/category-level questions, resolve population ambiguity (dedup vs not, which `cat_lvl`, scope of average, zero-price handling) with extra probes before spending ANSWER; exact-match scoring punishes one wrong interpretation. [Task 1]

- Symptom: submitted `0` and benchmark replied "Question 1: INCORRECT. Your answer: 0. Exploratory queries used: 6." Cause: the epoch-unit interpretation was flawed somewhere despite min/max probes. Fix: before answering "count rows with date >= X" on an unfamiliar epoch column, compute a full per-year histogram under the chosen interpretation and test s/ms/µs/ns for domain plausibility. [Task 7]
- Do not submit 0 from a single-unit interpretation. Apply a per-row `CASE` on `length(ts)` in the final count, not merely in min/max probes, and consider that the short 58-row minority-precision bucket may use a different epoch than assumed. [Task 7]
- Precise per-row shape to adapt: convert each bucket by `length(ts)`, verify the resulting date-range and year-count distribution, and only then apply the `>= 2031` predicate. Avoid a uniform `strftime('%Y', ts/1000, 'unixepoch')` conversion when mixed lengths are present. [Task 7]
- Symptom: `ERROR: no such column: price` wasted query 1/15. Cause: guessed an unabbreviated column on `items_g2`. Fix: run `PRAGMA table_info` or read `sqlite_master.sql` before the first data query; this benchmark uses `prc`, `prc_usd`, `ttl`, and `avg_rtg`. [Task 7]
- Symptom: `ERROR: no such column: f.item_id` in a `fdbk_g3` join wasted one query. Cause: assumed an `item_id` join instead of checking DDL. Fix: use `fdbk_gN.ref_id` (FK to `items_gN.ref_id`) directly, or dump the relevant `CREATE TABLE` statements before writing the join. [Task 10]
- Symptom: submitted `20.92` and benchmark replied "Question 2: INCORRECT. Your answer: 20.92. Exploratory queries used: 3." Cause: the run computed from `items_g2.prc_usd` without verifying the electronics table/category mapping or choosing between `prc` and `prc_usd`. Fix: first list and inspect tables, confirm category discrimination through `main_cat` or related evidence, and identify the intended dollar column before spending budget on the final calculation. [Task 8]
- Symptom: submitted `8164` after only 2 of 15 queries and benchmark replied "Question 3: INCORRECT. Your answer: 8164. Exploratory queries used: 2." Cause: the run trusted the stored mixed-epoch CASE without running the required `length(ts)` histogram/year verification and did not independently re-test price-column semantics. Fix: reserve 1–2 queries for `SELECT LENGTH(ts), COUNT(*), MIN(ts), MAX(ts) FROM fdbk_g1 GROUP BY LENGTH(ts);` plus a year histogram, then re-verify the boundary predicate and price column before the final count. [Task 6]
