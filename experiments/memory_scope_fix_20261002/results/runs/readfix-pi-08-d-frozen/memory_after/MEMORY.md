[ledger-sales-total v3] ledger.csv sales total: read export.json for real parser params
Task: "total amount of sales rows in the ledger.csv export". ALWAYS trust the workspace export.json for parser params; do not trust hardcoded params from prior notes (they can be stale/decoys).

Observed real export.json: {"encoding":"utf-16","delimiter":"\t","preamble_lines":2,"file":"ledger.csv"}. Note delimiter is a TAB and encoding utf-16 (BOM fffe), NOT utf-8/comma as an earlier note claimed.

read_file on the utf-16 CSV returns only a hex prefix (prefix_hex) and byte size; decode/just use parse_csv instead.

Correct call: parse_csv(path="ledger.csv", encoding="utf-16", delimiter="\t", skip_lines=2). It then treats the next line as header (columns category, amount) and returns data rows alternating sales/refund.

Semantics confirmed by task wording + prior note: "total amount of sales rows" = SUM(amount) where category=="sales" (a sum of amounts, not a row count).

Current data: sales rows 13,31,49,67 -> 160 (4 sales rows; refunds 22,40,58,76 ignored). Result: {"answer":160}.

[experience-tool-quirks v1] experience tool usage quirks
experience `put` requires a non-empty `id` string; omitting it fails with {"error":"KeyError: 'id'"} even though the schema lists id as optional. Always pass op,id,title,content. Reusing an existing id fully replaces (bumps version). Use op:"search" (query, or empty) to list entries, op:"get" with id to read one, op:"delete" with id to remove.