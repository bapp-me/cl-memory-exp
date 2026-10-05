v1

## User Profile

No stable human preferences are recorded yet. Current memory is from a benchmarking workflow in `/state/work/database`: answer database questions with exact values while conserving an explicit exploratory-query budget. Evidence so far comes from a failed clbench SQLite task rather than user conversation, so avoid treating its technical lessons as broader personal preferences.

## User preferences

- No human-user preference evidence is currently recorded; existing harness constraints are exact-value ANSWER submission, a 15-query exploratory cap, and a 50-row result cap.

## General Tips

- For unfamiliar SQLite timestamp columns, first list tables with `sqlite_master`, identify domain/category tables, then test epoch units s/ms/µs/ns with length, min, max, and a full year histogram. Never submit a `>= date` count based on a single-unit interpretation, especially when digit lengths are mixed.
- In clbench, g1 is office products, g2 electronics, and g3 musical instruments; feedback is in `fdbk_gN`, and `datetime(ts,'unixepoch')` is NULL for large epoch integers unless the value is divided first.

## What's in Memory

### /state/work/database

#### 2026-10-05

- clbench office-product timestamp count: `fdbk_g1`, `items_g1`, timestamp precision, `unixepoch`, `strftime`, year 2031
  - desc: Failed benchmark query counting office-product reviews dated >= 2031; search here for the anonymized schema and mixed-epoch lessons in `cwd=/state/work/database`.
  - learnings: 13-digit `fdbk_g1.ts` rows looked like ms (2001–2023), 58 15-digit rows looked like µs but that was unverified; a uniform `ts/1000` count returned 0 and was marked INCORRECT. Build a per-`length(ts)` CASE and year histogram, testing alternate units before answering.

### Older Memory Topics

#### /state/work/database

- Benchmark harness behavior: 15-query cap, 50-row cap, exact-value ANSWER
  - desc: Operational constraints for clbench database tasks in `cwd=/state/work/database`; use to plan query count before exploration.
