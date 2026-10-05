v1

## User Profile

No stable human preferences are recorded yet. Current memory is from a benchmarking workflow in `/state/work/database`: answer database questions with exact values while conserving an explicit exploratory-query budget. Evidence includes failed and successful clbench SQLite tasks rather than user conversation, so avoid treating their technical lessons as broader personal preferences.

## User preferences

- No explicit human-user preference is currently recorded; the strongest benchmark-derived rule is to re-verify timestamp units, date boundaries, category, rating source, and price-column semantics on the current instance before answering, even when a stored playbook provides the schema and conversion.

## General Tips

- In clbench, first consult `MEMORY.md` and `skills/clbench-sql-benchmark/SKILL.md`; one related question was solved in 2/15 queries without schema exploration. Then discover schemas with `sqlite_master` only as needed, verify category through table content rather than table ordinal, verify units (`prc` versus `prc_usd`), and distinguish feedback-derived `AVG(rtg)` from stored `items.avg_rtg`.
- For exact-count numeric thresholds, submit the count from the plain direct predicate rather than an epsilon-adjusted diagnostic; verified `ABS(stored_actual)>1` was CORRECT while `>1.000000001` was 4 rows low.
- For unfamiliar SQLite timestamps, test s/ms/µs/ns with type, length, min/max, and a full year histogram. Never submit a date-filtered count from a single-unit interpretation or from a stored conversion alone, especially when digit lengths are mixed.
- `datetime(ts,'unixepoch')` is NULL for large epoch integers unless divided first. In this DB, g1 is verified as office products; feedback is in `fdbk_gN`.

## What's in Memory

### /state/work/database

#### 2026-10-05

- clbench stored-versus-actual office rating difference: `items_g1`, `fdbk_g1`, `avg_rtg`, `AVG(rtg)`, `ABS`, boundary floating point, answer `2715`
  - desc: Newest successful question — count office products whose stored `avg_rtg` differs from the feedback-derived mean by more than 1 star in `cwd=/state/work/database`.
  - learnings: Kept stored `items_g1.avg_rtg` separate from actual feedback `AVG(rtg)`; submitted the plain `ABS(diff)>1` count (2715), not an epsilon diagnostic (2711), because 333 rows were within ±1e-6 of the boundary.
- clbench electronics price/review-rating count: `items_g2`, `fdbk_g2`, `prc_usd`, `prc`, `main_cat`, `All Electronics`, answer `8`
  - desc: Successful benchmark question — electronics products >$50 with >=5 reviews and average review rating <3.0 in `cwd=/state/work/database`.
  - learnings: g2 is electronics despite no exact `main_cat='Electronics'`; verified `prc = prc_usd * 100` and used feedback-derived `AVG(rtg)` (8) rather than `items.avg_rtg` (3) or cents (`prc > 50`, 26). A 4-query consolidated workflow was CORRECT.
- clbench 2022 office review count with price in (20, 200): `fdbk_g1`, `items_g1`, `prc`, `8164`, `length(ts)`, strict boundaries
  - desc: Failed question; office-product reviews filtered to CY2022 and strict price boundaries in `cwd=/state/work/database`.
  - learnings: The stored mixed-epoch CASE was reused without fresh length/year verification and answered `8164` after only 2/15 queries; the answer is known INCORRECT and the minority 15-digit/µs interpretation, boundary predicate, or price-column choice remain suspects.
- clbench office-product timestamp count: `fdbk_g1`, `items_g1`, timestamp precision, `unixepoch`, `strftime`, year 2031
  - desc: Failed benchmark query counting office-product reviews dated >= 2031; search here for the anonymized schema and mixed-epoch lessons in `cwd=/state/work/database`.
  - learnings: 13-digit `fdbk_g1.ts` rows looked like ms (2001–2023), 58 15-digit rows looked like µs but that was unverified; a uniform `ts/1000` count returned 0 and was marked INCORRECT. Build a per-`length(ts)` CASE and year histogram, testing alternate units before answering.
- clbench electronics median: `items_g2`, `prc_usd`, median, `ROW_NUMBER`, `ERROR: no such column: price`, 20.92
  - desc: Failed Question 2 computing non-zero electronics prices; search for abbreviated item schema and the table/category verification trap in `cwd=/state/work/database`.
  - learnings: `items_g2` has `prc` and `prc_usd`, not `price`; the working ROW_NUMBER median returned 20.92 but was INCORRECT because the electronics table/category mapping was never verified.
- Benchmark harness behavior: 15-query cap, 50-row cap, exact-value ANSWER, INCORRECT-only feedback
  - desc: Operational constraints for clbench database tasks in `cwd=/state/work/database`; use to plan query count before exploration.

### Older Memory Topics

#### /state/work/database

- clbench SQLite benchmark playbook: `sqlite_master`, `main_cat`, timestamp units, median, `CLBENCH_ACTION`
  - desc: Consolidated schema/category, timestamp, median, and budget workflow; use `skills/clbench-sql-benchmark/SKILL.md` before answering similar questions with `cwd=/state/work/database`.
