---
name: clbench-spanning-categories
description: "CLBENCH \"reviewers spanning N different top-level categories\" is NOT taxn cat_lvl=0 — that gave 0.00 and was scored WRONG; GT likely uses items.main_cat"
metadata:
  node_type: memory
  type: feedback
  originSessionId: bc192934-8570-4965-a370-1da5f424ad61
  modified: 2026-10-04T18:47:37.973Z
---

2026-10-04 Q15/40: "What percentage of office product reviewers have left reviews on products spanning 2 or more different top-level categories?" I used the taxonomy: `taxn_g1` `cat_lvl=0` had exactly 2 roots (Office Products 17825 items, Office Electronics 29 items), found 115 uids touched an Office Electronics item and only 9 spanned both roots, so 9/346790 = 0.00% → answered **0.00 → INCORRECT** (6 queries used).

**Why:** the ground-truth reference implementation evidently does not resolve "top-level categories" through `taxn` `cat_lvl=0` for this reviewer-spanning template — a 2-root taxonomy makes the answer degenerate, which a benchmark generator would not ship. The likely GT source is `items.main_cat` (the noisy per-item category column, ~33 distinct values in that instance, including NULLs and cross-dataset values) joined via `fdbk.ref_id → items.ref_id`, counting DISTINCT main_cat per uid — which yields a non-trivial percentage.

**How to apply:** for "spanning N different categories / top-level categories" questions about reviewers or products, compute the `items.main_cat` reading as the primary candidate; only fall back to `taxn` lvl0 if main_cat is absent from that instance's table set. If one reading produces a degenerate answer (0.00, 100.00, single-row category sets), treat that as a red flag and check the other before submitting — see [[clbench-schema-conventions]] (which documents that lvl0 *is* the right tool for identifying which gN is which dataset, a different use). Related: [[clbench-timestamp-naive-ms]].

Perf note from the same question: one `JOIN` of `fdbk_g1` (377k rows) against a materialized `cat_lvl=0` CTE (17.8k rows) finished inside the 10s timeout, but 4 repeated joins / stacked `IN (SELECT ...)` subqueries in one statement timed out — keep big-table joins to one per query.
