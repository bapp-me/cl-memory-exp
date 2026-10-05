v1

## User Profile

No stable human preferences are recorded yet. Current memory is from a benchmarking workflow in `/state/work/database`: answer database questions through `CLBENCH_ACTION` with exact values while conserving an explicit 15-query exploratory budget. Evidence includes failed and successful clbench SQLite tasks rather than user conversation, so avoid treating benchmark-derived technical rules as broader personal preferences.

## User preferences

- For clbench questions, read `MEMORY.md` and `skills/clbench-sql-benchmark/SKILL.md` before SQL, then use one consolidated verification query before ANSWER. Recent memory-first solves: Q28 2/15, Q29 4/15, Q30 6/15; Q12/Q16/Q17/Q19 each 1/15.
- If wording, category scope, price column, verification flag, or threshold population is ambiguous, compare candidate interpretations in one query and reserve budget before ANSWER. Q23–Q27 show the one-shot failure pattern.
- If multiple semantic interpretations remain after consolidation, choose by wording and benchmark conventions before ANSWER—not by candidate order. Q31, Q33, Q34, Q36, and Q40 show that the instance locks after `instance_complete=true`; a corrected answer is impossible.
- Submit only the exact requested value, with the requested rounding/format and no explanation.

## General Tips

- Use saved g1=office, g2=electronics, g3=musical instruments facts, but dump compact schema when table/column names are new: instances drift (`attrs_g3_legacy`, `product_attributes_g3`, `items_g1.status`, `fdbk_g1.verified_status`, `fdbk_g3.review_year`, `items_g2.prc_v2`). Verify `attr_val`, join on `ref_id`, and category through `main_cat`/taxonomy—not table membership alone.
- Confirm money and flag semantics per instance: `items_g2.prc` was cents and `prc_usd` dollars, but Q21's "list price" used `prc/100`; `fdbk_g2.vrf='true'` does not transfer to integer `fdbk_g1.vrf`, whose missing TEXT label is `verified_status IS NULL`.
- In g1, `vrf=1` and `verified_status='verified'` have different populations. Map "verified-purchase" semantically and compare materially different variants; Q40's vrf=1 answer failed while verified_status was the leading untested candidate.
- Do not lowercase/normalize brand values unless asked: Q36's exact-spelling count 761 was the likely intended answer and case-normalized 749 was INCORRECT.
- `CLBENCH_ACTION QUERY` accepts exactly one statement; failed multi-statement calls consume budget. Include every outer-referenced column in CTE SELECT lists.
- For ambiguous population/format questions, probe rounded versus full precision, NULL-as-zero versus exclusion, zero/nonzero prices, `prc` versus `prc_usd`, `main_cat` versus taxonomy, review-count sources, rows versus distinct refs/items, and strict/inclusive thresholds in one side-by-side query.
- For timestamps, inspect type, length distribution, min/max, and a year/month histogram under the chosen conversion; `fdbk_g1/g2.ts` are INTEGER while `fdbk_g3.ts` is TEXT. For reviewer spans, avoid materialized DISTINCT `uid` sets and use single-pass `GROUP BY f.uid`.
- Prefer grouped conditional aggregation or materialized/LEFT JOIN CTEs over correlated scans; wide feedback queries can hit the 10-second timeout.
- For heavy office multi-variant aggregations, pre-aggregate per `ref_id`, then CROSS JOIN a flags/values CTE; for per-brand anti-joins, pre-materialize DISTINCT matching `ref_id` sets instead of correlated `NOT EXISTS`.

## What's in Memory

### /state/work/database

#### 2026-10-05

- clbench Q31–Q40 interpretation, brand, date-source, and price-band tasks: `94.8`, `116.71`, `980`, `430`, `0.58`, `749`, `36.1`, `2636`, `Computers & Accessories`, `0.23`
  - desc: Ten newest Q31–Q40 runs covering verified-purchase flags, electronics MAD, current-vs-legacy brand attributes, exact brand spelling, 2022 date sources, taxonomy wording, and office price bands in `cwd=/state/work/database`.
  - learnings: Q32/Q35/Q39 are CORRECT in 1/1/2 queries; Q31/Q33/Q34/Q36/Q37/Q38/Q40 are INCORRECT. Use raw brand spelling, dedicated `fdbk_g3.review_year` cautiously, all price columns, and semantic verification before ANSWER. Leading untested variants include Q31 94.8, Q34 514, Q38 2775, and Q40 0.22.
- clbench Q21–Q30 median, timestamp, schema-drift, and verification tasks: `21.99`, `10.3`, `1370`, `Yamaha`, `52.94`, `86`, `10.0`, `1.11`, `6.1`, `1.1`
  - desc: Ten Q21–Q30 runs covering `prc_v2`, even medians, missing full timestamps, mean-relative thresholds, brand thresholds, electronics scope, only-unverified products, attribute-feed ratios, and `verified_status`/`status` in `cwd=/state/work/database`; now the second-newest benchmark day.
  - learnings: Q21=21.99 CORRECT (`items_g2.prc/100`, `img_ct>0`, `prc>0`), Q28=1.11 CORRECT, Q29=6.1 CORRECT (`items_g1.status='archived'`), Q30=1.1 CORRECT (`verified_status IS NULL`). Do not resubmit Q22=10.3, Q23=1370, Q24=Yamaha, Q25=52.94, Q26=86, or Q27=10.0; their populations/flags need side-by-side probes. [ad-hoc note]
- clbench Q11–Q20 memory-first solves and failures: `attrs_g3`, `Brand`, `Fender`, `Date First Available`, `5254`, `AVG(rtg)`, `4.128218677940046`, `prc_usd`, `52.95666246454459`, `LEFT JOIN`, `0.12`, `LENGTH(body)`, `10.22`
  - desc: Ten Q11–Q20 runs covering brands, listing dates, feedback averages, priced/unpriced gaps, body-length percentages, reviewer spans, timestamps, and discontinued attributes in `cwd=/state/work/database`.
  - learnings: Q12/Q16/Q17/Q19 used 1/15, Q11/Q14 3/15, and Q20 6/15. Q18's full-precision average, Q13's interpretation, and Q15's taxonomy-level `0.00` are known INCORRECT; check population/format before ANSWER.
- clbench one-shot and performance shields: `single-statement`, `schema drift`, `main_cat LIKE '%Electronics%'`, `vrf`, `10s timeout`, `GROUP BY f.uid`
  - desc: Cross-task query-shape, interpretation, and timeout safeguards in the clbench skill and MEMORY block.
  - learnings: Compare all plausible populations in one query; inspect query diagnostics before ANSWER. Use grouped conditional aggregation/materialized CTEs, not correlated feedback scans or materialized `uid` pair sets.

### Older Memory Topics

#### /state/work/database

- clbench Q1–Q10 aggregate, taxonomy, timestamp, and median lessons: `taxn_g2`, `Computers & Accessories`, `24.44`, `vrf='true'`, `101.8`, `item_id`, `1832`, `avg_rtg`, `2715`, `All Electronics`, `8164`, `2031`, `ROW_NUMBER`, `20.92`, `NOT EXISTS`, `267`, `2020-01`
  - desc: Established schemas, join keys, price units, rating sources, attribute coverage, mixed epochs, medians, and category/population traps for Q1–Q10.
- clbench SQLite benchmark playbook: `CLBENCH_ACTION`, `sqlite_master`, `ref_id`, `attrs_gN`, `taxn_gN`, `prc_usd`, `AVG(rtg)`, `length(ts)`, median, query budget
  - desc: Consolidated procedure and verification checklist in `skills/clbench-sql-benchmark/SKILL.md`; use before any related clbench question in `cwd=/state/work/database`.
