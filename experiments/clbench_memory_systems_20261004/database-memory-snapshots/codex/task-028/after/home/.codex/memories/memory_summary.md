v1

## User Profile

No stable human preferences are recorded yet. Current memory is from a benchmarking workflow in `/state/work/database`: answer database questions with exact values while conserving an explicit 15-query exploratory budget. Evidence includes failed and successful clbench SQLite tasks rather than user conversation, so avoid treating benchmark-derived technical rules as broader personal preferences.

## User preferences

- For clbench questions, read `MEMORY.md` and `skills/clbench-sql-benchmark/SKILL.md` before SQL, then run one consolidated verification query before ANSWER. This memory-first pattern produced several 1/15-query solves; Q11 and Q14 used 3/15.
- Submit only the exact requested value, with the requested rounding/format and no explanation.

## General Tips

- Use saved schema/category facts first: g1=office, g2=electronics, g3=musical instruments; feedback joins items on `ref_id`, not `item_id`. Verify category through content (`main_cat`, `taxn_gN.cat_nm`, `cat_lvl`), never table ordinal.
- Confirm column semantics before querying: `items_g2.prc` is cents and `prc_usd` is dollars; g1 has `prc` only. Distinguish feedback `AVG(rtg)` from stored `items.avg_rtg`, and `fdbk_g2.vrf='true'` from numeric flags.
- For ambiguous averages or percentages, unit checks are insufficient. Spend leftover budget on rounding/full precision, NULL-as-zero versus exclusion, category scope, rows versus distinct items, alternate review-count sources, and other `cat_lvl`/`main_cat` populations.
- For reviewer-span queries, do not materialize `SELECT DISTINCT uid` pair sets; `fdbk_gN.uid` has no index and five such probes timed out. Use single-pass `GROUP BY f.uid` with `COUNT(DISTINCT i.main_cat)`.
- For timestamps, inspect type, digit-length distribution, min/max, and a year/month histogram under the chosen conversion. Never trust a stored conversion alone; `fdbk_g1/g2.ts` are INTEGER while `fdbk_g3.ts` is TEXT.
- Consolidate row counts, category counts, exclusions, boundary/min/max checks, and candidate answers into one query. Check UNION column widths and CTE aliases before spending budget.

## What's in Memory

### /state/work/database

#### 2026-10-05

- clbench Q11–Q20 memory-first solves and failures: `attrs_g3`, `Brand`, `Fender`, `Date First Available`, `5254`, `AVG(rtg)`, `4.128218677940046`, `prc_usd`, `52.95666246454459`, `LEFT JOIN`, `0.12`, `LENGTH(body)`, `10.22`
  - desc: Ten Q11–Q20 runs covering brands, listing dates, feedback averages, priced/unpriced gaps, body-length percentages, reviewer spans, timestamps, and discontinued attributes in `cwd=/state/work/database`.
  - learnings: Memory-first consolidated queries solved Q12/Q16/Q17/Q19 in 1/15, Q11/Q14 in 3/15, and Q20 in 6/15. Q18's full-precision average, Q13's `NOT EXISTS`+nonzero-price interpretation, and Q15's taxonomy-level `0.00` are known INCORRECT; probe population/format alternates before ANSWER.
- clbench Q15 reviewer-span performance trap: `fdbk_g1`, `items_g1`, `uid`, `main_cat`, `COUNT(DISTINCT i.main_cat)`, `358837`, `10s timeout`, `1.87`
  - desc: Failed office-reviewer multi-top-level-category percentage run; contains the database's reusable query-timeout shield.
  - learnings: Avoid materialized `uid` DISTINCT pair sets. The single-pass grouped reviewer-span query ran ~5–6 seconds; use remaining budget to compare taxonomy versus `main_cat` reviewer populations rather than submitting a degenerate `0.00`.
- clbench percentage/average interpretation shields: `prc_usd`, `NULL handling`, `ROUND`, `NOT EXISTS`, `fdbk_stats_gN`, `main_cat`, `cat_lvl`, exact-match scoring
  - desc: Recurring Q8/Q13/Q18 failure pattern in `cwd=/state/work/database`: semantically plausible but unprobed population or output interpretation.
  - learnings: Treat zero/NULL handling, category scope, DISTINCT/row basis, review-source, and rounding as separate hypotheses. Unit consistency alone does not validate the answer.

### Older Memory Topics

#### /state/work/database

- clbench Q1–Q10 aggregate, taxonomy, timestamp, and median lessons: `taxn_g2`, `Computers & Accessories`, `24.44`, `vrf='true'`, `101.8`, `item_id`, `1832`, `avg_rtg`, `2715`, `All Electronics`, `8164`, `2031`, `ROW_NUMBER`, `20.92`, `NOT EXISTS`, `267`, `2020-01`
  - desc: Established schemas, join keys, price units, rating sources, attribute coverage, mixed epochs, medians, and category/population traps for Q1–Q10 in `cwd=/state/work/database`.
- clbench SQLite benchmark playbook: `CLBENCH_ACTION`, `sqlite_master`, `ref_id`, `attrs_gN`, `taxn_gN`, `prc_usd`, `AVG(rtg)`, `length(ts)`, median, query budget
  - desc: Consolidated procedure and verification checklist in `skills/clbench-sql-benchmark/SKILL.md`; use before answering any related clbench question with `cwd=/state/work/database`.
