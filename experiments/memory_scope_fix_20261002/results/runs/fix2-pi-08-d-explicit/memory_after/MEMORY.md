[ledger-sales-total v5] CSV ledger sales total (read export.json parser params first)
Task: "total amount of sales rows in ledger.csv export" -> {"answer": number}; SUM of amount over category=='sales', not a count.

Applicability: only when an export.json governs ledger.csv in the workspace. Parser params VARY per export - never assume utf-8/comma/no-preamble.

Steps:
1. read_file export.json -> file, encoding, delimiter, preamble_lines.
2. parse_csv(path=export.file, encoding=export.encoding, delimiter=<the delimiter>, skip_lines=export.preamble_lines).
   - delimiter must be EXACTLY 1 character (write \t in tool-call JSON for a tab). Multi-char fails with TypeError 'delimiter must be a 1-character string'.
   - skip_lines must equal preamble_lines or preamble/header rows leak in.
3. Rows have columns category,amount (amounts are strings, e.g. "13"); rows alternate sales/refund. Sum amount where category=='sales'.

Observed runs: config {"encoding":"utf-16","delimiter":"\t","preamble_lines":2,"file":"ledger.csv"} parsed cleanly. Sales 12,30,48,66 -> 156; another run sales 13,31,49,67 -> 160. Always emit {"answer": number}.

[experience-tool-quirks v1] experience tool usage quirks
experience `put` requires a non-empty `id` string; omitting it fails with {"error":"KeyError: 'id'"} even though the schema lists id as optional. Always pass op,id,title,content. Reusing an existing id fully replaces (bumps version). Use op:"search" (query, or empty) to list entries, op:"get" with id to read one, op:"delete" with id to remove.