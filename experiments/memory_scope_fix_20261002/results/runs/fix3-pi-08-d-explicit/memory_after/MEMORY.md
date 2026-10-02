[ledger-sales-total v5] CSV ledger sales total (read export.json parser params first)
Task pattern: compute "total amount of sales rows in ledger.csv export" -> return {"answer": number}. It is a SUM of the amount column over sales rows, NOT a row count.

Applicability: only for a ledger.csv governed by an export.json in the workspace. Parser params VARY per export - never assume utf-8/comma/no-preamble. (An earlier note hard-coded those defaults; a default parse_csv would raise UnicodeDecodeError byte 0xff for a utf-16 export and mis-split tab fields.) Configs seen: {"encoding":"utf-16","delimiter":"\t","preamble_lines":2,"file":"ledger.csv"} on two occasions.

Steps:
1. read_file export.json to get file, encoding, delimiter, preamble_lines.
2. parse_csv(path=export.file, encoding=export.encoding, delimiter=<tab>, skip_lines=export.preamble_lines).
   - delimiter must be EXACTLY 1 character, else TypeError 'delimiter must be a 1-character string'. For a tab export pass a single tab (write \t in the tool-call JSON) so it decodes to one tab; multi-character values such as tab+newline fail.
   - skip_lines must match preamble_lines (observed 2), else preamble/header rows leak into the data.
3. parse_csv rows have columns category,amount (amounts may be strings, e.g. "12"); rows alternate sales/refund. Sum amount where category=='sales'.

Observed examples: sales 12,30,48,66 -> 156. sales 13,31,49,67 -> 160.
Always emit {"answer": number}.

[experience-tool-quirks v1] experience tool usage quirks
experience `put` requires a non-empty `id` string; omitting it fails with {"error":"KeyError: 'id'"} even though the schema lists id as optional. Always pass op,id,title,content. Reusing an existing id fully replaces (bumps version). Use op:"search" (query, or empty) to list entries, op:"get" with id to read one, op:"delete" with id to remove.