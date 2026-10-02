[local-api-ledger-workflow v2] Local mock API tasks (ledger) — workflow
Task pattern: "Using the local ledger API, compute X over all items, return JSON {answer}".

Workflow:
1. list_files -> usually only api.json. read_file api.json for service docs.
2. GET /info returns {version, documentation} only.
3. GET /items is paginated. IMPORTANT: pagination style depends on service version reported by /info and described in api.json.
   - v2: CURSOR-based. Params: limit (max 3) and cursor (opaque token, e.g. "pos:3"). Response {items:[...], total, next_cursor}; next_cursor null ends list. `page` is IGNORED (returns first page again).
   - older: page/next_page style. ALWAYS trust api.json for the current version; my prior note about next_page was for an older version.
4. Loop passing the returned next_cursor until next_cursor is null. Don't trust a single page.
5. Filter by predicate (e.g. active==true) then aggregate (sum amounts).

Gotchas:
- Unknown/extra query params are silently ignored (same first page) — no multi-ledger concept; "current ledger" is flavor only.
- Item ids have a ledger prefix (item-4-N); prefix varies per task instance.
- Compute/verify arithmetic carefully.

Example (v2): items 1-8 amounts 11,18,25,32,39,46,53,60; active 11,18,32,39,53,60; inactive 25,46 -> sum 213 -> {"answer":213}.