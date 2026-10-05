---
name: clbench-brand-line-feed-vs-export
description: "Q33 \"brand in current feed but no brand line in older export\" — exact attr_key='Brand' on both sides (1240) was WRONG; compute the brandish-LIKE variant too"
metadata:
  node_type: memory
  type: project
  originSessionId: 197a2585-0b22-4e6b-812f-cbde359dfc51
  modified: 2026-10-04T19:55:40.318Z
---

Q33 (2026-10-04): g3 musical group, `product_attributes_g3` (current product-facts feed, 202,543 rows) vs `attrs_g3_legacy` (older attribute export, 182,566 rows). Question: distinct products with brand info in the feed but no brand line at all in the export. Answered 1240 (exact `attr_key='Brand'` present in feed, absent in legacy) → INCORRECT. Alternative computed in the same pass: any brandish key (`attr_key LIKE '%rand%'` incl. `'Brand Name'`) on both sides = 1153.

Verified facts that held: brand values all non-empty on the feed side; every feed ref_id ∈ items_g3 (items-scoping changes nothing); PA feed total 202,543 matches the [[clbench-current-feed-vs-legacy-export]] ratio numerator.

**Why:** the strict literal reading failed, so the GT apparently binds the broader brandish reading (or a variant I did not compute, e.g. legacy has no row at all for the product, or legacy brand rows with empty attr_val treated as "no brand line").

**How to apply:** for "brand line" / attribute-line presence questions across sibling attribute tables, pack ALL of these in one single-pass query (CTE per table, conditional MAX(CASE...)): (1) exact key both sides, (2) LIKE-brandish both sides, (3) no legacy row AT ALL for the product, (4) legacy line present but value empty/NULL, (5) items-scoped variant. Exact-key is no longer the default favorite — see [[clbench-packed-single-pass-variants]].
