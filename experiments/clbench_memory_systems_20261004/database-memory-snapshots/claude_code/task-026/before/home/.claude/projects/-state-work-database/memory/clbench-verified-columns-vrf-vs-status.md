---
name: clbench-verified-columns-vrf-vs-status
description: "fdbk_g1 dual verified columns — cross-tab shows verified_status is vrf with NULL-masked rows; \"verified purchase\" binds to vrf (complete boolean)"
metadata:
  node_type: memory
  type: project
  originSessionId: 7551b2f6-4ade-4825-8f19-b8b89ab35e56
  modified: 2026-10-04T19:32:08.869Z
---

CLBENCH instance (Q26, office/g1): fdbk_g1 has BOTH `vrf INTEGER` and `verified_status TEXT` (g2/g3 have only vrf). Cross-tab: verified='verified'⇒vrf=1 (246267), 'unverified'⇒vrf=0 (17963), plus NULL-status rows split vrf=1:105478 / vrf=0:7764 — NO conflicts; verified_status = vrf with ~30% rows NULL-masked. Chose `vrf` for "zero verified purchases among all their reviews" (complete boolean, canonical name across datasets; vstatus would make the GT NULL-semantics-dependent: SUM=0→85, NOT EXISTS→376, all-explicitly-unverified→43). Also: my single-scan agreement probe `SUM((vrf=1)=(verified_status='verified'))` returned garbage (17963 = unverified count, algebraically impossible) — don't trust that probe pattern, cross-tab instead. Related: [[clbench-list-price-column-ambiguity]], [[clbench-schema-conventions]].

**Why:** dual-column ambiguity with NULLs; the partial TEXT column is the distractor, the complete boolean binds.
**How to apply:** if a later question says verified/unverified purchases, use vrf (g1: 1=verified, 0=unverified); if 83-style answers are rejected, fall back to vstatus readings (85/376/43). Beware correlated NOT EXISTS on fdbk tables — engine times out at 10s; use GROUP BY aggregates.
