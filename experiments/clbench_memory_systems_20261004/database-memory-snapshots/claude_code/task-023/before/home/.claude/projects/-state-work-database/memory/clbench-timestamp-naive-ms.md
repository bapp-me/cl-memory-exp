---
name: clbench-timestamp-naive-ms
description: "CLBENCH ts handling — naive-ms GT verified once, but an ms-window count of 0 is a red flag: verify the group mapping and the seconds reading before ever answering 0"
metadata:
  node_type: memory
  type: project
  originSessionId: ba33a75b-c157-41dd-82ea-f085d5462271
  modified: 2026-10-04T18:37:19.252Z
---

Two conflicting data points on how the CLBENCH ground truth evaluates date-window counts over `fdbk_*` INTEGER `ts` columns:

1. **Naive-ms rule (verified correct once).** Session ba33a75b, "reviews in year 2031+": ts was mixed 13-digit ms (majority) + 15-digit µs (minority). I normalized units → 0 → INCORRECT. GT used one naive numeric comparison vs the ms threshold, so µs rows rendered as far-future (year ~33000) and counted (58 rows). Do not per-row-normalize when 13-digit values dominate.

2. **0-count trap (hit 2026-10-04, Q12/40).** "Electronics reviews in Q4 2021". `fdbk_g2` had 77,022 rows, ts ∈ [1008272539, 999482389000] — **no 13-digit values at all** (ms-reading = 1970-01-12..2001-09-08). The ms window [1633046400000, 1640995200000) contained 0 rows; I answered 0 → **INCORRECT**. So GT > 0 came from either (a) the electronics group was NOT g2 in that instance (I skipped the per-instance `taxn cat_lvl=0` check — mapping is NOT stable across instances, see [[clbench-schema-conventions]]) and GT was a naive-ms count on another group's table, or (b) GT read the 10-digit values as unix SECONDS ([1633046400, 1640995200) ⊂ observed range).

**Why:** the naive-ms semantics only reproduce the GT when the target table actually holds 13-digit ms values; applying it to a table whose range can't reach the window silently produces a confident 0.

**How to apply:** (1) never trust the g1/g2/g3 ↔ category mapping across instances — verify `taxn_gN WHERE cat_lvl=0` and MIN/MAX ts of the target `fdbk_gN` in one composite query; (2) evaluate date windows with conditional SUMs of BOTH readings (ms bounds and seconds bounds) in one query; (3) answer the nonzero reading — naive-ms stays the default only where 13-digit values dominate; (4) only answer 0 when both readings are 0 AND the group mapping is verified. Unresolved: which reading wins if both are nonzero.
