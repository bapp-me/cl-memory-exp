---
name: clbench-current-feed-vs-legacy-export
description: "current feed vs older export" for a category maps to two sibling attribute tables in that group; GT = raw row counts
metadata:
  type: project
---

In CLBENCH, "lines of product attribute data in the current feed vs the older attribute export" for a named category = the group's TWO sibling attribute tables (e.g. `product_attributes_g3` current, `attrs_g3_legacy` older; only one group had a legacy twin). GT binds to raw `COUNT(*)` of each and their ratio rounded to 2dp (Q28: 202543/182566 = 1.11).

**Why:** attribute tables are key/value rows (ref_id, attr_key, attr_val), so "lines of data" = rows; NULL/empty values were tiny (~0.08%) and every row-based variant (non-empty, distinct ref_id, distinct key pairs) rounded to the same 2dp — only distinct attr_key counts (672/648=1.04) differ, and that's not "lines of data".

**How to apply:** list tables, pick the two attribute tables in the named group (verify group with dominant main_cat per [[clbench-schema-conventions]]), count both rows in one packed scalar-subquery SELECT; no need to chase NULL or distinct-row variants unless the ratio is near a rounding boundary.
