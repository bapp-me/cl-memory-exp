v1

## User Profile

No stable human preferences are recorded yet. Current memory is from a benchmarking workflow in `/state/work/database`: answer database questions with exact values while conserving an explicit exploratory-query budget. Evidence comes from failed clbench SQLite tasks rather than user conversation, so avoid treating their technical lessons as broader personal preferences.

## User preferences

- No human-user preference evidence is currently recorded; existing harness constraints are exact-value ANSWER submission, a 15-query exploratory cap, and a 50-row result cap.

## General Tips

- In clbench, first discover schemas with `sqlite_master`; verify the requested category through table content rather than table ordinal, and verify value units (for example `prc` versus `prc_usd`). Related skill: `skills/clbench-sql-benchmark/SKILL.md`.
- For unfamiliar SQLite timestamps, test s/ms/µs/ns with type, length, min/max, and a full year histogram. Never submit a `>= date` count from a single-unit interpretation, especially when digit lengths are mixed.
- `datetime(ts,'unixepoch')` is NULL for large epoch integers unless divided first. In this DB, g1 is verified as office products; feedback is in `fdbk_gN`.

## What's in Memory

### /state/work/database

#### 2026-10-05

- clbench electronics median: `items_g2`, `prc_usd`, median, `ROW_NUMBER`, `ERROR: no such column: price`, 20.92
  - desc: Failed Question 2 computing non-zero electronics prices; search for abbreviated item schema and the table/category verification trap in `cwd=/state/work/database`.
  - learnings: `items_g2` has `prc` and `prc_usd`, not `price`; the working ROW_NUMBER median returned 20.92 but was INCORRECT because the electronics table/category mapping was never verified.
- clbench office-product timestamp count: `fdbk_g1`, `items_g1`, timestamp precision, `unixepoch`, `strftime`, year 2031
  - desc: Failed benchmark query counting office-product reviews dated >= 2031; search here for the anonymized schema and mixed-epoch lessons in `cwd=/state/work/database`.
  - learnings: 13-digit `fdbk_g1.ts` rows looked like ms (2001–2023), 58 15-digit rows looked like µs but that was unverified; a uniform `ts/1000` count returned 0 and was marked INCORRECT. Build a per-`length(ts)` CASE and year histogram, testing alternate units before answering.
- Benchmark harness behavior: 15-query cap, 50-row cap, exact-value ANSWER, INCORRECT-only feedback
  - desc: Operational constraints for clbench database tasks in `cwd=/state/work/database`; use to plan query count before exploration.

### Older Memory Topics

#### /state/work/database

- clbench SQLite benchmark playbook: `sqlite_master`, `main_cat`, timestamp units, median, `CLBENCH_ACTION`
  - desc: Consolidated schema/category, timestamp, median, and budget workflow; use `skills/clbench-sql-benchmark/SKILL.md` before answering similar questions with `cwd=/state/work/database`.
