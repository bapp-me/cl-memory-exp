---
name: clbench-sql-benchmark
description: Use when answering clbench SQLite database questions via CLBENCH_ACTION, especially schema/category mapping, timestamps, medians, or exact-value results.
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
3. From the schemas, identify candidate item and feedback tables. Verify the requested category using table content (especially `main_cat`) or another discriminating column; do not infer it from the table ordinal.
4. Confirm the exact requested column and value domain. For money, distinguish integer/local price columns from explicit dollar columns such as `prc_usd`; note g1 has `prc` only, while g2 has both `prc` and `prc_usd`.
5. For timestamps, inspect type, `MIN`, `MAX`, and digit-length distribution; test seconds/milliseconds/microseconds/nanoseconds. Build a per-`length(ts)` conversion `CASE` and a year histogram before applying a date predicate. Do not submit any date-filtered result from a stored conversion alone.
6. For medians, use a CTE filtering nulls and zeros as required, `ROW_NUMBER() OVER (ORDER BY price)`, and `ROUND(AVG(price),2)` over `rn IN ((n+1)/2, (n+2)/2)`.
7. Run one consolidated verification query that reports row counts, group/category counts, null/zero exclusions, min/max, and the candidate answer whenever possible.
8. Submit only the exact requested value with ANSWER. Treat `INCORRECT` as undiagnosed failure rather than evidence of any particular mistake.

## Efficiency plan

- Combine schema and category-discrimination checks when a single query can stay below the 50-row result cap.
- Avoid separate probes for information available in one grouped query.
- Stop exploration when the candidate value has passed semantic, unit, category, and row-count checks.
- For date-filtered answers, reserve at least one query for the `length(ts)` histogram and one for the year distribution under the chosen conversion, even if memory supplies the schema and CASE.

## Pitfalls and fixes

- `ERROR: no such column: price` -> abbreviated schema -> read `sqlite_master.sql` or `PRAGMA table_info`; expected names include `prc`, `prc_usd`, `ttl`, and `avg_rtg`.
- `INCORRECT` after a timestamp count -> mixed or wrong epoch units -> rebuild with per-`length(ts)` conversion and verify the year histogram for domain plausibility.
- `INCORRECT` after reusing a stored timestamp conversion -> skipped per-question verification -> run the current instance's length histogram and year counts, and re-check strict/inclusive boundaries and price semantics.
- `INCORRECT` after an item calculation -> unverified table/category mapping -> map all item tables and their `main_cat` values before recomputing.
- NULL dates from `datetime(ts,'unixepoch')` -> large epoch integers were not divided -> divide by the appropriate power of 1,000.

## Verification checklist

- Confirm each selected table belongs to the requested category with evidence.
- Confirm the selected column matches the requested unit and domain.
- Confirm timestamp units with a full histogram rather than only min/max probes.
- Confirm date bounds and boundary inclusivity match the question (for example 2022 is `1640995200..1672531199`).
- Confirm exclusions (null, zero, category, date) and show row counts before answering.
- Confirm the ANSWER format exactly matches the question and contains no explanation.
