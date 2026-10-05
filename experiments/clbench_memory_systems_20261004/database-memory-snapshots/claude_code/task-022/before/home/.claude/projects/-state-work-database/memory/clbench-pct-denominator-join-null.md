---
name: clbench-pct-denominator-join-null
description: "For \"what % of reviews are for products priced above X\" questions, GT appears to drop NULL-price/failed-join rows from the DENOMINATOR (inner-join semantics), not keep them"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 9e334100-63d4-4cbe-95ad-1712ff4d41b6
  modified: 2026-10-04T19:09:06.011Z
---

Q22 (musical instruments, g3): "What percentage of musical instrument reviews that are missing a full event timestamp are for products priced above the average list price across all priced instruments?" I answered with the literal denominator (ALL reviews with ts IS NULL, 85990; numerator 9847 → 11.5) and it was marked INCORRECT. The un-tried reading: denominator restricted to reviews whose item has a price (INNER JOIN + prc IS NOT NULL, 60550; 9847/60550 → 16.3).

**Why:** When the condition in the numerator involves a joined column that can be NULL, a straightforward GT query is usually written as one SELECT with JOIN + `prc > (subquery)` filters, which silently removes NULL-price rows from the denominator too.

**How to apply:** For "what percentage of A are B(c)" where B(c) needs a joined attribute that may be NULL, compute BOTH: (a) literal denominator = all of A, (b) restricted denominator = A rows satisfying the join/NULL-requirements of B. If the two differ, prefer (b) — the inner-join reading — first. Related: [[clbench-spanning-categories]], [[clbench-dataset-scoped-questions]] (degenerate/literal readings there also lost to the "obvious single-SQL" reading).
