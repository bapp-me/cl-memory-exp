---
name: clbench-packed-single-pass-variants
description: Multi-variant aggregate comparisons over big fdbk tables must be one CTE pass with conditional AVGs — separate UNION ALL join passes hit the 10s query timeout
metadata:
  node_type: memory
  type: feedback
  originSessionId: be9d8ded-3c64-4b6f-af22-1a7926288112
  modified: 2026-10-04T19:45:09.059Z
---

Packing 5 variants (readings of a comparison question) as five `UNION ALL` branches each doing its own `fdbk_gN ⋈ items_gN` join over ~377K rows exceeded the benchmark's 10s query timeout (Q30, fdbk_g1).

**Why:** each branch is a full join pass; 5 passes ≈ 1.9M B-tree lookups plus repeated TRIM/LENGTH scans. The timeout burns a query attempt from the budget.

**How to apply:** put the join in a single `WITH t AS (...)` referenced once, compute all per-row quantities (LENGTH, LENGTH(TRIM(...)), boolean flags) in the CTE, then emit every variant's group averages with conditional aggregation in one SELECT: `AVG(CASE WHEN <variant cond> THEN len END)` (NULL rows are auto-excluded) and `SUM(<bool>)` for counts. Verify this works — it ran in well under the timeout. Also confirmed there: LENGTH(TRIM(body)) = LENGTH(body) exactly, so trimming is moot when bodies lack edge whitespace. Related: [[clbench-verified-columns-vrf-vs-status]], [[clbench-schema-conventions]].
