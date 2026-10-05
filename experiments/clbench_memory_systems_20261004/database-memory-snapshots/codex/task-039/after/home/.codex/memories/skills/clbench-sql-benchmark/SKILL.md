---
name: clbench-sql-benchmark
description: Use when answering clbench SQLite database questions via CLBENCH_ACTION, especially schema/category mapping, attributes, taxonomy/category hierarchy, reviewer spans, verified-review/body metrics, timestamps, medians, or exact-value results.
argument-hint: "[question]"
disable-model-invocation: true
allowed-tools: [Bash, Read, Grep, Glob]
---

# Answer a clbench SQLite benchmark question

## When to use

- The task is a clbench database question submitted through `CLBENCH_ACTION`.
- The database has unfamiliar tables, abbreviated columns, category datasets, epoch timestamps, or an exact numeric/text answer.
- Do not use for databases with known schemas outside this benchmark.

## Inputs to gather

- The exact question, requested value, rounding rule, and whether null/zero records should be excluded.
- The remaining exploratory-query budget and the current `CLBENCH_ACTION` invocation syntax.
- Database scope: product data may use table groups and feedback tables; timestamps and category labels require verification.

## Procedure

1. If `CLBENCH_ACTION` is unknown, discover it first; all QUERY and ANSWER calls must go through it.
2. Read `MEMORY.md` and this skill before SQL. Reuse their schema/category facts and identify which checks, if any, still require a query.
3. Spend the first query on compact schema/category discovery only when memory leaves a needed gap: `SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;`. From the schemas, identify candidate item, feedback, and supporting tables, including `attrs_gN` and `taxn_gN` for attribute-coverage, brand, listing-date, and category-hierarchy questions. Verify the requested category using table content (`main_cat`, `cat_nm`, and relevant `cat_lvl`) or another discriminating column; do not infer it from the table ordinal. In this benchmark, g1 is office, g2 is electronics, and g3 is musical instruments.
4. Confirm the exact requested column, join key, and value domain. Feedback tables join items through `ref_id` (the FK to `items_gN.ref_id`), not `item_id`. For money, distinguish integer/local price columns from explicit dollar columns such as `prc_usd`; note g1 has `prc` only, while g2 can have `prc`, `prc_usd`, and `prc_v2`, and g3 `prc` was dollars in one drifted instance. In verified electronics instances, "list price" repeatedly meant `prc/100` over `prc>0`, not `prc_usd` (Q21 median 21.99; Q32 MAD 116.71); Q39 correctly compared all three price-column variants in one query.
5. For timestamps, inspect type, `MIN`, `MAX`, and digit-length distribution; test seconds/milliseconds/microseconds/nanoseconds. Build a per-`length(ts)` conversion `CASE` and a year histogram before applying a date predicate. Do not submit any date-filtered result from a stored conversion alone. `fdbk_g1.ts` and `fdbk_g2.ts` are INTEGER; drifted `fdbk_g3` may store `ts` as TEXT while also providing explicit `review_year`/`review_month`—use populated dedicated columns, but remember Q38 showed `review_year` and raw `ts` year could disagree substantially.
6. For "average review rating", decide whether the requested value is feedback-derived `AVG(rtg)` per item or the stored `items.avg_rtg`; in the verified electronics and office questions, feedback-derived `AVG` was correct. If the wording explicitly contrasts the stored average with the actual mean of review scores, keep those sources distinct (`items.avg_rtg` versus feedback `AVG(rtg)`).
7. For verified-review and body-text questions, inspect the flag's actual type/domain: `fdbk_g2.vrf` is TEXT and `vrf='true'` was correct, while `fdbk_g1.vrf` is integer 1/0 and `fdbk_g1.verified_status` TEXT has domain NULL/`unverified`/`verified`. These g1 flags are not equivalent—vrf=1 includes verified_status NULL rows. For "verified-purchase", map wording semantically and compare materially different variants before ANSWER; Q31 favored vrf=1, while Q40's failed vrf answer made verified_status the leading untested candidate. When wording says a label is missing, use the TEXT column `IS NULL`. Exclude NULL/blank bodies and compare raw versus trimmed lengths when whitespace semantics could matter.
8. For "how many more distinct values" questions, identify which identifier is primary/non-primary or the FK, then compute `COUNT(DISTINCT a) - COUNT(DISTINCT b)` and return both distinct counts in the same consolidated query.
9. For exact-count numeric-threshold questions, compute the candidate with the plain direct predicate (for example `ABS(stored_actual)>1`). Do not substitute an epsilon such as `>1.000000001` in the submitted predicate; verify boundaries separately only if needed.
10. For "not represented in attributes at all", map the exact supporting table and use `NOT EXISTS` on its `ref_id`; the verified office query was `SELECT COUNT(DISTINCT f.ref_id) FROM fdbk_g1 f WHERE f.ref_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM attrs_g1 a WHERE a.ref_id = f.ref_id)`.
11. For brand or listing-date attributes, first verify the exact supporting-table names, `attr_key`, and value column. The office value column is `attrs_g1.attr_val`; drifted musical instances may use `product_attributes_g3` plus `attrs_g3_legacy` instead of plain `attrs_g3`. Normalize noisy keys, but do not lowercase brand values unless the question explicitly asks to treat spellings as one brand: Q36's exact-spelling count 761 was correct and the case-normalized 749 was incorrect. For "current feed" versus "legacy export", verify which physical table each phrase means and probe table/population variants before ANSWER.
12. For reviewer-span questions on this DB, avoid materializing `SELECT DISTINCT uid` pair sets; they repeatedly hit the 10-second timeout because `fdbk_gN.uid` is not indexed. Use single-pass `GROUP BY f.uid` with `COUNT(DISTINCT i.main_cat)` inside a subquery, and preserve budget for alternate population interpretations.
13. For medians, use a CTE filtering nulls and zeros as required, `ROW_NUMBER() OVER (ORDER BY price)`, and `AVG`—not MIN or MAX—over `rn IN ((n+1)/2, (n+2)/2)`. Use `ROUND`/scaling only to produce the requested format.
14. Run one consolidated verification query that reports row counts, group/category counts, null/zero exclusions, min/max, and the candidate answer whenever possible. For heavy office multi-variant aggregations, pre-aggregate per item (`GROUP BY i.ref_id` with conditional SUM/COUNT), then CROSS JOIN a flags/values CTE; a raw multi-scope UNION over the full feedback join can exceed 10 seconds. For per-brand anti-joins, pre-materialize DISTINCT matching `ref_id` sets rather than using correlated `NOT EXISTS`.
15. Submit only the exact requested value with ANSWER. Treat `INCORRECT` as undiagnosed failure rather than evidence of any particular mistake. After `instance_complete=true`, the instance is locked: later QUERY/ANSWER calls can fail with `Mcp error: -32603: HTTPError`, so resolve interpretation before the first answer.
16. For item-aggregate questions, the proven four-query shape is: schema dump; one UNION-ALL per group joining items to per-`ref_id` feedback aggregates grouped by `main_cat` with candidate answers; targeted narrowing on the candidate group; then one wide unit/semantic verification.
17. For category-hierarchy, average, or percentage questions, verify population and format semantics separately: compare taxonomy levels (`cat_lvl`), `cat_nm` versus `main_cat`, DISTINCT versus row counts, zero/NULL price handling, rows versus distinct items, and requested rounding/full-precision output before answering. Unit checks alone do not validate an interpretation. Wording matters: `cat_lvl=1` grouped by `cat_nm` was CORRECT for "broadest category label (taxonomy level just below department)" in Q39, but not for every taxonomy question such as Q8. For "electronics", whole-table versus `main_cat` scope remains a recurring fork.
18. For "active" or "archived" products, check `items_g1.status` first; Q29 validated `status='archived'`, while discontinued attrs gave a different incorrect percentage. Q26's alternate "active" population remained unresolved, so enumerate active/discontinued/zero-review variants when those words are ambiguous.
19. For category wording such as "electronics", do not trust table membership alone. In one drifted instance, `items_g2` rows spanned `AMAZON FASHION`..`Video Games`, and only 3,646 of 14,954 `img_ct>=3` rows matched `main_cat LIKE '%Electronics%'`. Include category-distribution diagnostics and alternate scoped answers in the same query.
20. For mean-relative thresholds, never reuse a known-bad mean/population from another question. Put NULL-as-zero, priced-only, `main_cat`, taxonomy, `prc` versus `prc_usd`, and distinct/ref variants into one side-by-side query before ANSWER.
21. For timestamp wording such as "missing full timestamp", inspect NULL/empty, length/format, conversion validity, and whether the denominator is reviews versus items. Do not resubmit a count based only on NULL/empty when the wording says "full" or "valid".
22. `CLBENCH_ACTION QUERY` executes exactly one SQL statement per call; failed multi-statement calls consume budget. Keep every column referenced by an outer query in the CTE SELECT list.

## Efficiency plan

- Combine schema and category-discrimination checks when a single query can stay below the 50-row result cap.
- Avoid separate probes for information available in one grouped query.
- Stop exploration when the candidate value has passed semantic, unit, category, and row-count checks.
- On related clbench questions, consult `MEMORY.md` and this skill before spending the query budget; validated runs answered in 2/15 queries with no schema query and in 3/15 queries with only a targeted group-schema dump.
- Recent memory-first solves include Q12/Q16/Q17/Q19 at 1/15, Q11/Q14 at 3/15, Q28 at 2/15, Q29 at 4/15, and Q30 at 6/15; use saved facts first, then consolidate checks rather than re-exploring. Q21 needed 13/15 after avoidable multi-statement and CTE errors.
- Newer validated efficient solves include Q32 (1/15), Q35 (1/15), and Q39 (2/15). One consolidated side-by-side query is often enough only when memory already resolves the semantic mapping; otherwise reserve another query before ANSWER.
- For date-filtered answers, reserve at least one query for the `length(ts)` histogram and one for the year distribution under the chosen conversion, even if memory supplies the schema and CASE.
- If a prior answer in the same family was INCORRECT, treat its population/format as a red flag, not a base to extend. A single extra consolidated interpretation query is cheaper than another one-shot failure.

## Pitfalls and fixes

- `ERROR: no such column: price` -> abbreviated schema -> read `sqlite_master.sql` or `PRAGMA table_info`; expected names include `prc`, `prc_usd`, `ttl`, and `avg_rtg`.
- `ERROR: no such column: f.item_id` -> feedback joined on the wrong identifier -> use `fdbk_gN.ref_id`, or dump the relevant `CREATE TABLE` DDL before writing the join.
- `ERROR: no such table: attrs_g2` or `attrs_g3` -> attrs support tables are not uniform across instances -> check `sqlite_master`; known names include `attrs_g1`, `attrs_g3_legacy`, and `product_attributes_g3`.
- `ERROR: You can only execute one statement at a time` -> QUERY contained multiple statements -> issue one statement per call and fold PRAGMA/schema facts into a compact CTE where possible.
- `ERROR: no such column: attr_value`, `v`, or an unexpected price column -> generic memory pattern/schema drift -> use `PRAGMA table_info` and the exact DDL (`attr_val`, `status`, `verified_status`, `prc_v2` are known drift/new-column examples).
- A reviewer-span query times out at 10 seconds -> materialized `uid`-DISTINCT pair sets with no `uid` index -> use single-pass `GROUP BY f.uid` with `COUNT(DISTINCT i.main_cat)` and reserve queries for alternate populations.
- `INCORRECT` after a timestamp count -> mixed or wrong epoch units -> rebuild with per-`length(ts)` conversion and verify the year histogram for domain plausibility.
- `INCORRECT` after reusing a stored timestamp conversion -> skipped per-question verification -> run the current instance's length histogram and year counts, and re-check strict/inclusive boundaries and price semantics.
- `INCORRECT` after an item calculation -> unverified table/category mapping -> map all item tables and their `main_cat` values before recomputing.
- `INCORRECT` after a taxonomy/category calculation (Q8, 24.44 via `taxn_g2.cat_lvl=1`) -> unresolved population/category-level interpretation -> probe alternate `cat_lvl`, `cat_nm`/`main_cat`, dedup, zero-price, and average-scope interpretations before resubmitting.
- `INCORRECT` after a plausible full-precision average (Q18, 52.95666246454459) -> population and/or exact format unresolved -> probe rounded versus full precision, NULL-as-zero versus exclusion, category scope, and rows versus distinct items while budget remains.
- `INCORRECT` after one plausible threshold/category/flag answer (Q23-Q27) -> ANSWER spent before comparing interpretations -> do not repeat that candidate; compute scoped, flag, identifier, and price-column variants together while budget remains.
- Candidate variants were computed but the first/lowest-level flag or normalized interpretation was submitted -> semantic mapping or benchmark grouping convention unresolved -> before ANSWER, match wording to the semantically best column and favor raw brand spellings unless the question says to normalize. Q31 failed at 66.3, Q34 at 430, Q36 at 749, and Q40 at 0.23 despite useful alternate counts.
- A wide feedback CTE times out at 10 seconds -> correlated subqueries or repeated scans over hundreds of thousands of rows -> use grouped conditional aggregation, scalar subqueries, or materialized/LEFT JOIN CTEs; test the cheapest split first if consolidation is expensive.
- Exact-count threshold differs by a few rows despite correct semantics -> floating-point values near the boundary and an epsilon was used -> resubmit only after recomputing with the plain direct predicate; a verified case had 333 rows within ±1e-6 and plain `>1` was CORRECT.
- NULL dates from `datetime(ts,'unixepoch')` -> large epoch integers were not divided -> divide by the appropriate power of 1,000.

## Verification checklist

- Confirm each selected table belongs to the requested category with evidence.
- For category hierarchy, confirm which `cat_lvl`/`cat_nm` or `main_cat` population the wording intends, and whether to deduplicate support-table rows.
- Confirm the selected column matches the requested unit and domain.
- Confirm the selected supporting table (for example `attrs_g1` for office attributes) and that absence means no matching `ref_id`.
- Confirm the rating source (feedback aggregate versus stored item rating) when both exist.
- Confirm the verification flag type and literal (`fdbk_g2.vrf='true'`) and whether body counts require non-empty text/trimming.
- Confirm the semantics of verification wording separately from flag mechanics: whether "verified purchases"/"verified reviews" means `vrf=1`, `verified_status='verified'`, or a hybrid count/average population.
- Confirm the exact supporting-table and column names (`attr_val`, `attr_key`, `items_g1.status`, `fdbk_g1.verified_status`, `items_g2.prc_v2`) for the current instance.
- Confirm explicit source labels: "stored average rating" means `items.avg_rtg`, while "actual mean of review scores" means feedback-derived `AVG(rtg)`.
- Confirm threshold predicates use the question's exact comparison (`>` versus `>=`) without accidental epsilon tightening.
- Confirm timestamp units with a full histogram rather than only min/max probes.
- Confirm date bounds and boundary inclusivity match the question (for example 2022 is `1640995200..1672531199`).
- Confirm exclusions (null, zero, category, date) and show row counts before answering.
- Confirm exact ANSWER formatting (rounded versus full precision, percentage decimals) and the intended population before spending the final answer.
- Confirm the ANSWER format exactly matches the question and contains no explanation.
