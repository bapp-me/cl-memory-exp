[local-api-ledger-workflow v1] Local mock API tasks (ledger) — workflow
Task pattern: "Using the local ledger API, compute X over all items, return JSON {answer}".

Workflow:
1. list_files -> usually only api.json. read_file api.json for service docs (endpoints, pagination rules).
2. GET /info returns service metadata only (version + documentation filename).
3. GET /items is paginated: params page (1-based), limit (max 3). Response: {items:[{id,amount,active}], total, next_page}. next_page null means end. ALWAYS loop pages until next_page is null; don't trust a single page. Here total=8 items across 3 pages (limit cap 3).
4. Filter by the requested predicate (e.g. active==true) then aggregate (sum amounts).

Gotchas:
- Unknown/extra query params (e.g. ledger=2) are silently ignored and return the same first page — no multi-ledger concept; "current ledger" is just flavor.
- Requesting a page past the end returns {items:[], next_page:null}.
- Item ids have a ledger prefix (item-1-N) but that alone doesn't imply selectable ledgers.
- Compute carefully; verify arithmetic.

Example: 8 items, active amounts 8,15,29,36,50,57 (inactive 22,43) -> sum 195 -> {"answer":195}.

[local-ledger-v2 v1] Local ledger API v2 — cursor pagination
Service: ledger, version 2 (api.json). Endpoints: /info -> {version, documentation}. /items -> {items:[{id,amount,active}], total, next_cursor}.
PAGINATION IS CURSOR-BASED in v2: query param `cursor` (token like "pos:3"), NOT `page` (page is ignored). limit max 3. Loop: first GET /items?limit=3, then follow next_cursor until null. Don't trust total or a single page.
Gotcha: extra/unknown params silently ignored. total=8 across 3 pages.
Workflow: list_files -> read api.json -> GET /info -> loop /items by next_cursor -> filter predicate (e.g. active==true) -> aggregate.
Example: active amounts 10,17,31,38,52,59 (inactive 24,45) -> 207 -> {"answer":207}.
If experience mentions page=..., that is v1; re-check api.json for current version.