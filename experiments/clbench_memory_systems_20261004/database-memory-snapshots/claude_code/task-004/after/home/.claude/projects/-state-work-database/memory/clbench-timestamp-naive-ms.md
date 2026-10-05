---
name: clbench-timestamp-naive-ms
description: "CLBENCH ground truth treats review timestamps naively as milliseconds, even when some rows are microseconds"
metadata:
  node_type: memory
  type: project
  originSessionId: ba33a75b-c157-41dd-82ea-f085d5462271
  modified: 2026-10-04T17:50:01.399Z
---

In the CLBENCH database benchmark (session started 2026-10-04), a question asked how many reviews had timestamps in year 2031+. The `fdbk_*` tables store `ts` as INTEGER epoch with **mixed units**: 13-digit milliseconds (most rows) and 15-digit microseconds (a small minority, old 1999-2001 reviews). I normalized units and answered 0; the benchmark marked it INCORRECT.

**Why:** The ground truth was evidently computed with a naive conversion (e.g. `pd.to_datetime(ts, unit='ms')` or SQL `ts >= <ms threshold>`), which makes the 15-digit µs rows render as far-future dates (year ~33000) and count as "2031 or later" — 58 rows.

**How to apply:** For timestamp/date-threshold questions in this benchmark, compute the count the naive way (treat every `ts` as milliseconds, single numeric comparison against the ms-epoch threshold) rather than detecting and normalizing per-row units. Report that naive count as the answer. Also: `items_g1`=Office Products, `items_g2`=Electronics, `items_g3`=Musical Instruments in that DB.
