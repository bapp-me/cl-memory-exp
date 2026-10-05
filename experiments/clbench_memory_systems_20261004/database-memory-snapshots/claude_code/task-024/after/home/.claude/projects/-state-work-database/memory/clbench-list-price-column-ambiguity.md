---
name: clbench-list-price-column-ambiguity
description: "CLBENCH: 'list price' questions are WRONG with prc when items_g2 also has prc_v2 — compute the metric under EVERY price column in one query before answering"
metadata:
  node_type: memory
  type: reference
  originSessionId: bc751919-efeb-4633-b517-d428ff68992c
  modified: 2026-10-04T19:23:35.169Z
---

Q23 (2026-10-04, electronics instance): "How many electronics products have a list price at least 15% higher than the mean list price across all electronics with a positive list price?" I answered the `prc` reading — **1035, marked INCORRECT** (5 queries).

That instance's `items_g2` had THREE price columns (earlier instances had only two — see [[clbench-schema-conventions]]):
- `prc` INTEGER cents — 6570 non-null, 0 nonpositive, 13430 NULL; mean(prc>0) = 9623.34¢, 1.15× threshold = 11066.85, count ≥ = **1035** (no boundary ties: nearest rows 11049 / 11091, so strict vs ≥ and float noise are irrelevant). ← the WRONG answer
- `prc_usd` REAL — exactly `prc/100` on all 6346 overlapping rows; NULL exactly when prc ≥ 50000¢. Its reading (mean over its own 6346 positive rows) = **1370**.
- `prc_v2` INTEGER — non-null on exactly the same 6570 rows as `prc`, ≈ **1.0102× `prc`** on average. Its reading was **NOT COMPUTED** — that was the regret.

Q25 (2026-10-04, same instance family): "average **list price in dollars** for electronics with ≥3 images (`img_ct` ≥ 3), ignore non-positive list price". Same three-column schema: `prc` cents, `prc_usd` = prc/100 but NULL for prc ≥ 50000¢ (188 expensive rows silently dropped → avg 52.94 on its subset vs 100.85 for prc/100 on all priced rows), `prc_v2` on exactly the prc>0 rows ≈1.0094×. Computed all three in ONE packed query → answered **`AVG(prc_v2)/100` = 101.80 → CORRECT** (2 queries). This CONFIRMS the prc_v2 binding and also that "in dollars" means ÷100 on the cents column (GT was NOT raw cents, NOT prc_usd).

**Why:** `prc_v2`'s profile fits "list price" semantics (same coverage as the real price, values ~1% higher = list ≥ selling). The question generator binds the phrase "list price" to `prc_v2` when it exists — now verified twice (Q23 wrong with prc, Q25 right with prc_v2). `prc` is only the safe default when `prc_v2` is absent (Q21 instance, "median list price in dollars", `prc`/100 = CORRECT, no prc_v2 recorded there). `prc_usd` is a distractor: exact prc/100 but truncated at $500, so its subset average skews low.

**How to apply:** if `items_g2` (or any group) carries more than one price column AND the question says "list price", compute the answer under EVERY price column (each with its own positive filter, plus ÷100 variants) in ONE packed SELECT of scalar subqueries before answering — never burn the answer on the `prc` reading alone. Rank: (1) `prc_v2` when present (CONFIRMED GT binding, ÷100 if question says "in dollars"); (2) `prc` (canonical, complete, ÷100) when prc_v2 is absent; (3) `prc_usd` (partial unit-variant distractor — never the GT).
