[local-api-ledger-workflow v2] Local mock API tasks (ledger) — workflow
Task pattern: "Using the local ledger API, compute X over all items, return JSON {answer}".

Workflow:
1. list_files -> usually only api.json. read_file api.json for service docs (endpoints, pagination rules).
2. GET /info returns service metadata only (version + documentation filename).
3. GET /items is paginated. ALWAYS loop to the end; never trust a single page. total=8 items, limit cap 3 => 3 pages.
4. Filter by predicate (e.g. active==true) then aggregate (sum amounts).

PAGINATION VARIES BY VERSION — read api.json each time:
- v1: params page (1-based) + limit; response {items,total,next_page}; next_page null = end.
- v2: CURSOR-based: {items,total,next_cursor}; param name is `cursor`, first request just {limit:3}, then pass cursor=next_cursor (e.g. "pos:3","pos:6").
- v2 doc says "page is ignored" — passing page=2 silently returns page 1. In general, unknown/ignored params (ledger=2, page) return the same first page; "current ledger" is just flavor, no multi-ledger concept.
- Requesting past the end returns {items:[], next_cursor:null} — useful sanity check.

Gotchas:
- Item ids carry a ledger prefix (item-N-M); that alone doesn't imply selectable ledgers.
- Compute carefully; verify arithmetic by re-summing.

Examples: v1: active 8,15,29,36,50,57 (inactive 22,43) -> 195. v2: active 11,18,32,39,53,60 (inactive 25,46) -> 213.