# Memory Index

- [environment.md](./environment.md) — Reusable DB facts: three disjoint 20k-item datasets (g1=Office, g2=Electronics, g3=Musical Instruments); review→item join key is `ref_id` (not `item_id`); `LENGTH(body)` counts characters; g2 price: `prc` is CENTS, `prc_usd` = prc/100 (USD), partial non-null coverage; no literal "list price" field. Includes scope and evidence, verified vs. inferred.
