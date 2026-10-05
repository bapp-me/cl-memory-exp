---
name: clbench-brand-threshold-priced-rows
description: "Q24 counterexample — \"brands with ≥50 products, highest avg price\" with a mostly-NULL prc column: counting ALL catalog rows (Yamaha) was WRONG; the ≥50 threshold likely binds to rows that actually have a price (→ Fender)"
metadata:
  node_type: memory
  type: project
  originSessionId: c099dd1f-9049-490f-ab98-2dd5ebf7a325
  modified: 2026-10-04T19:19:21.956Z
---

CLBENCH Q24 (musical-instrument brands, ≥50 products, highest avg list price): items_g3 was 60% NULL on prc (7949/20000 priced). I computed brands via product_attributes_g3 attr_key IN ('Brand','Brand Name'), HAVING COUNT(*)>=50 on all joined rows, ORDER BY AVG(prc) DESC → Yamaha (143 items, 42 priced, avg 422.82) — marked INCORRECT.

**Why:** When the price column is mostly NULL, the GT's "at least fifty different products" threshold appears to bind to products that actually have a price (Yamaha had only 42 priced → excluded; Fender, 243 items / 71 priced / avg 362.20, becomes top). Under that reading the answer would be Fender.

**How to apply:** For "brand/group with ≥N products + highest avg price" questions, first check the NULL rate of the price column. If it's high, compute the ranking BOTH ways in one query — HAVING COUNT(*)>=N (all rows) and HAVING COUNT(prc)>=N (priced rows only) — and prefer the priced-rows reading when the two disagree; also cross-check both attr tables (product_attributes_g3 vs *_legacy) since brand coverage differs. See [[clbench-list-price-column-ambiguity]] and [[clbench-dataset-scoped-questions]].
