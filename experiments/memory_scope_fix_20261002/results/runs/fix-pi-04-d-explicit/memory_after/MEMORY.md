[local-api-ledger-workflow v2] Local mock API tasks (ledger) — v1 page-based workflow
APPLICABILITY: Use ONLY when workspace api.json shows "version": 1 (page-based pagination). If api.json or GET /info reports version 2+, this entry does NOT apply — use the cursor/next_cursor workflow in entry local-api-ledger-workflow-v2 instead. ALWAYS read api.json and check the version field before applying this entry.

Task pattern: "Using the local ledger API, compute X over all items, return JSON {answer}".

Workflow (v1):
1. list_files -> usually only api.json. read_file api.json for service docs (endpoints, pagination rules).
2. GET /info returns service metadata only (version + documentation filename).
3. GET /items is paginated: params page (1-based), limit (max 3). Response: {items:[{id,amount,active}], total, next_page}. next_page null means end. ALWAYS loop pages until next_page is null; don't trust a single page. Here total=8 items across 3 pages (limit cap 3).
4. Filter by the requested predicate (e.g. active==true) then aggregate (sum amounts).

Gotchas (v1):
- Unknown/extra query params (e.g. ledger=2) are silently ignored and return the same first page — no multi-ledger concept; "current ledger" is just flavor.
- Requesting a page past the end returns {items:[], next_page:null}.
- Item ids have a ledger prefix (item-1-N) but that alone doesn't imply selectable ledgers.
- Compute carefully; verify arithmetic.

Example (v1): 8 items, active amounts 8,15,29,36,50,57 (inactive 22,43) -> sum 195 -> {"answer":195}.

NOTE: A v2 task (api.json version 2) was once wrongly approached with this page-based entry; the /items response there used next_cursor and ignored page. Hence the strict version gate above.

[local-api-ledger-workflow-v2 v1] Local mock ledger API — v2 cursor pagination workflow
Task pattern: "Using the local ledger API, compute X (e.g. sum of amounts for active items) over all items, return JSON {answer number}".

Workflow:
1. list_files -> only api.json. read_file api.json for service docs.
2. Check the "version" field! Endpoint spec varies by version.
3. GET /info returns {version, documentation} metadata only.
4. GET /items paginated. ALWAYS loop until terminal cursor is null; never trust one page. total tells the expected count (e.g. 8).

v2 (observed): limit max 3; CURSOR-based. Response: {items:[{id,amount,active}], total, next_cursor}. Pass next_cursor back as ?cursor=<token>&limit=3. next_cursor null ends list. `page` param is IGNORED. Cursor tokens look like "pos:3", "pos:6" (offset-style).
v1 (older): page-based with next_page; page 1-based, limit max 3.

Gotchas:
- Unknown/extra query params silently ignored -> returns same first page. Beware mixing page+cursor (page ignored in v2).
- Requesting past the end returns {items:[], next_cursor:null}.
- Ids have prefix item-<ledger>-N; no multi-ledger selection concept.
- Filter by predicate (active==true) then aggregate.

Example v2: 8 items; active amounts 10,17,31,38,52,59 (inactive 24,45) -> sum 207 -> {"answer":207}.
Example v1: active 8,15,29,36,50,57 -> 195.