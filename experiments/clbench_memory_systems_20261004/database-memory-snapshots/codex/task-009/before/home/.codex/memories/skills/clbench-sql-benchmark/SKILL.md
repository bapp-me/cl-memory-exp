---
name: clbench-sql-benchmark
description: Use when answering clbench SQLite database questions via CLBENCH_ACTION, especially schema/category mapping, taxonomy/category hierarchy, verified-review/body metrics, timestamps, medians, or exact-value results.
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
2. Spend the first query on compact schema discovery: `SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;`.
3. From the schemas, identify candidate item, feedback, and supporting tables, including `taxn_gN` for category-hierarchy questions. Verify the requested category using table content (`main_cat`, `cat_nm`, and relevant `cat_lvl`) or another discriminating column; do not infer it from the table ordinal.
4. Confirm the exact requested column and value domain. For money, distinguish integer/local price columns from explicit dollar columns such as `prc_usd`; note g1 has `prc` only, while g2 has both `prc` and `prc_usd`. In this benchmark, `items_g2.prc` is cents and equals `prc_usd * 100`.
5. For timestamps, inspect type, `MIN`, `MAX`, and digit-length distribution; test seconds/milliseconds/microseconds/nanoseconds. Build a per-`length(ts)` conversion `CASE` and a year histogram before applying a date predicate. Do not submit any date-filtered result from a stored conversion alone.
6. For "average review rating", decide whether the requested value is feedback-derived `AVG(rtg)` per item or the stored `items.avg_rtg`; in the verified electronics question, feedback-derived `AVG` was correct. If the wording explicitly contrasts the stored average with the actual mean of review scores, keep those sources distinct (`items.avg_rtg` versus feedback `AVG(rtg)`).
7. For verified-review and body-text questions, inspect the flag's actual type/domain: in this benchmark, `fdbk_g2.vrf` is TEXT and `vrf='true'` was correct. Exclude NULL/blank bodies (`body IS NOT NULL AND TRIM(body)<>''`), and compare raw `LENGTH(body)` with `LENGTH(TRIM(body))` in one consolidated query when whitespace semantics could matter.
8. For "how many more distinct values" questions, identify which identifier is primary/non-primary or the FK, then compute `COUNT(DISTINCT a) - COUNT(DISTINCT b)` and return both distinct counts in the same consolidated query.
9. For exact-count numeric-threshold questions, compute the candidate with the plain direct predicate (for example `ABS(stored_actual)>1`). Do not substitute an epsilon such as `>1.000000001` in the submitted predicate; verify boundaries separately only if needed.
10. For medians, use a CTE filtering nulls and zeros as required, `ROW_NUMBER() OVER (ORDER BY price)`, and `ROUND(AVG(price),2)` over `rn IN ((n+1)/2, (n+2)/2)`.
11. Run one consolidated verification query that reports row counts, group/category counts, null/zero exclusions, min/max, and the candidate answer whenever possible.
12. Submit only the exact requested value with ANSWER. Treat `INCORRECT` as undiagnosed failure rather than evidence of any particular mistake.
13. For item-aggregate questions, the proven four-query shape is: schema dump; one UNION-ALL per group joining items to per-`ref_id` feedback aggregates grouped by `main_cat` with candidate answers; targeted narrowing on the candidate group; then one wide unit/semantic verification.
14. For category-hierarchy or percentage questions, verify population semantics separately: compare taxonomy levels (`cat_lvl`), `cat_nm` versus `main_cat`, DISTINCT versus row counts, zero/NULL price handling, and whether "average" is category-local or scope-wide before answering.

## Efficiency plan

- Combine schema and category-discrimination checks when a single query can stay below the 50-row result cap.
- Avoid separate probes for information available in one grouped query.
- Stop exploration when the candidate value has passed semantic, unit, category, and row-count checks.
- On related clbench questions, consult `MEMORY.md` and this skill before spending the query budget; validated runs answered in 2/15 queries with no schema query and in 3/15 queries with only a targeted group-schema dump.
- For date-filtered answers, reserve at least one query for the `length(ts)` histogram and one for the year distribution under the chosen conversion, even if memory supplies the schema and CASE.

## Pitfalls and fixes

- `ERROR: no such column: price` -> abbreviated schema -> read `sqlite_master.sql` or `PRAGMA table_info`; expected names include `prc`, `prc_usd`, `ttl`, and `avg_rtg`.
- `INCORRECT` after a timestamp count -> mixed or wrong epoch units -> rebuild with per-`length(ts)` conversion and verify the year histogram for domain plausibility.
- `INCORRECT` after reusing a stored timestamp conversion -> skipped per-question verification -> run the current instance's length histogram and year counts, and re-check strict/inclusive boundaries and price semantics.
- `INCORRECT` after an item calculation -> unverified table/category mapping -> map all item tables and their `main_cat` values before recomputing.
- `INCORRECT` after a taxonomy/category calculation (Q8, 24.44 via `taxn_g2.cat_lvl=1`) -> unresolved population/category-level interpretation -> probe alternate `cat_lvl`, `cat_nm`/`main_cat`, dedup, zero-price, and average-scope interpretations before resubmitting.
- Exact-count threshold differs by a few rows despite correct semantics -> floating-point values near the boundary and an epsilon was used -> resubmit only after recomputing with the plain direct predicate; a verified case had 333 rows within ±1e-6 and plain `>1` was CORRECT.
- NULL dates from `datetime(ts,'unixepoch')` -> large epoch integers were not divided -> divide by the appropriate power of 1,000.

## Verification checklist

- Confirm each selected table belongs to the requested category with evidence.
- For category hierarchy, confirm which `cat_lvl`/`cat_nm` or `main_cat` population the wording intends, and whether to deduplicate support-table rows.
- Confirm the selected column matches the requested unit and domain.
- Confirm the rating source (feedback aggregate versus stored item rating) when both exist.
- Confirm the verification flag type and literal (`fdbk_g2.vrf='true'`) and whether body counts require non-empty text/trimming.
- Confirm explicit source labels: "stored average rating" means `items.avg_rtg`, while "actual mean of review scores" means feedback-derived `AVG(rtg)`.
- Confirm threshold predicates use the question's exact comparison (`>` versus `>=`) without accidental epsilon tightening.
- Confirm timestamp units with a full histogram rather than only min/max probes.
- Confirm date bounds and boundary inclusivity match the question (for example 2022 is `1640995200..1672531199`).
- Confirm exclusions (null, zero, category, date) and show row counts before answering.
- Confirm the ANSWER format exactly matches the question and contains no explanation.
