[ledger-sales-total v5] CSV ledger sales total (read export.json parser params first)
Task pattern: compute "total amount of sales rows in ledger.csv export" -> return {"answer": number}. It is a SUM of the amount column over sales rows, NOT a row count.

Applicability: only for a ledger.csv governed by an export.json in the workspace. Parser params VARY per export - never assume utf-8/comma/no-preamble.

Steps:
1. read_file export.json to get file, encoding, delimiter, preamble_lines.
2. parse_csv(path=export.file, encoding=export.encoding, delimiter=<tab, exactly 1 char>, skip_lines=export.preamble_lines).
   - delimiter must be EXACTLY 1 character, else TypeError 'delimiter must be a 1-character string'. For a tab export pass a single tab in the tool-call JSON so it decodes to one tab; multi-char values fail.
   - skip_lines must match preamble_lines, else preamble/header rows leak into the data.
   - utf-16 + tab + preamble_lines 2 has been observed; a default utf-8/comma parse raises UnicodeDecodeError byte 0xff and mis-splits fields.
3. Rows have columns category,amount (amounts may be strings, e.g. "13"); rows alternate sales/refund. Sum amount where category=='sales'.

Observed examples: sales 13,31,49,67 -> 160; earlier 12,30,48,66 -> 156.
Always emit {"answer": number}.

[experience-tool-quirks v1] experience tool usage quirks
experience `put` requires a non-empty `id` string; omitting it fails with {"error":"KeyError: 'id'"} even though the schema lists id as optional. Always pass op,id,title,content. Reusing an existing id fully replaces (bumps version). Use op:"search" (query, or empty) to list entries, op:"get" with id to read one, op:"delete" with id to remove.