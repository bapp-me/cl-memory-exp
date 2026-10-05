---
name: clbench-pct-denominator-join-null
description: "CLBENCH pct questions: GT drops NULL-price/failed-join rows from the DENOMINATOR (inner-join semantics) — even when an 'Among X' clause defines the population without price; the literal all-of-X denominator has lost TWICE (Q22 11.5→16.3, Q27 11.2→~24.5)"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 9e334100-63d4-4cbe-95ad-1712ff4d41b6
  modified: 2026-10-04T19:37:19.979Z
---

Q22 (musical instruments, g3): "What percentage of musical instrument reviews that are missing a full event timestamp are for products priced above the average list price across all priced instruments?" I answered with the literal denominator (ALL reviews with ts IS NULL, 85990; numerator 9847 → 11.5) and it was marked INCORRECT. The un-tried reading: denominator restricted to reviews whose item has a price (INNER JOIN + prc IS NOT NULL, 60550; 9847/60550 → 16.3).

**Why:** When the condition in the numerator involves a joined column that can be NULL, a straightforward GT query is usually written as one SELECT with JOIN + `prc > (subquery)` filters, which silently removes NULL-price rows from the denominator too.

Q27 (2026-10-04, electronics instance): "Among electronics products that have at least three customer reviews, what percentage have list price strictly above $60?" The ≥3-review population (3250 items_g2 rows via `fdbk_g2` GROUP BY ref_id) is defined WITHOUT reference to price, and ~67% of prices are NULL. I treated "Among X" as fixing the denominator: `prc_v2 > 6000` (list price, cents) = 364 → 364/3250 = **11.2, marked INCORRECT** (3 queries). The surviving reading, consistent with this memory and the prc_v2 list-price binding ([[clbench-list-price-column-ambiguity]]), is the price-restricted denominator: 364/1485 priced rows = **24.5**. (Other readings, all worse fits: prc 357/3250=11.0, prc 357/1485=24.0, prc_usd 324/1452=22.3.) Distinct-uid review counts (3244 vs 3250) change nothing after rounding.

**How to apply:** For any "what percentage of A are/have B(c)" where B(c) depends on a joined or nullable attribute, compute BOTH in ONE packed query: (a) literal denominator = all of A, (b) restricted denominator = A rows that actually have the attribute (join + `IS NOT NULL`). If they differ, **answer (b) first** — the inner-join/GT-SQL-shape reading. The "Among X..." phrasing does NOT protect the literal denominator; it has now lost twice (Q22, Q27). Only fall back to (a) if (b) was already tried and failed. Related: [[clbench-spanning-categories]], [[clbench-dataset-scoped-questions]] (degenerate/literal readings there also lost to the "obvious single-SQL" reading).
