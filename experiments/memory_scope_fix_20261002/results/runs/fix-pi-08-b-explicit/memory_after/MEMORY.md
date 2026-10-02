[ledger-sales-total v5] CSV ledger sales total (read export.json parser params first)
Task: compute "total amount of sales rows in ledger.csv export" -> return {"answer": number}. SUM of amount column over rows where category=='sales', NOT a row count.

Applicability: only for a ledger.csv governed by an export.json in the workspace. Parser params VARY per export - never assume utf-8/comma/no-preamble. Confirmed variants observed: (a) {"encoding":"utf-16","delimiter":"\t","preamble_lines":2,"file":"ledger.csv"} - default parse raised UnicodeDecodeError byte 0xff and mis-split tab fields; (b) {"encoding":"utf-8","delimiter":",","preamble_lines":0}. So ALWAYS read export.json first.

Steps:
1. read_file export.json to get file, encoding, delimiter, preamble_lines.
2. parse_csv(path=export.file, encoding=export.encoding, delimiter=<the 1-char delimiter>, skip_lines=export.preamble_lines).
   - delimiter must be EXACTLY 1 character, else TypeError 'delimiter must be a 1-character string'. For a tab export pass a single tab (write \t in the tool-call JSON) so it decodes to one tab; a multi-character value such as tab+newline fails.
   - skip_lines must match preamble_lines, else preamble/header rows leak into the data.
3. parse_csv rows have columns category,amount (amounts may be strings, e.g. "11"); rows typically alternate sales/refund. Sum amount (int/float) where category=='sales'.

Observed examples: sales 12,30,48,66 -> 156; sales 11,29,47,65 -> 152.
Always emit {"answer": number}.

[experience-tool-quirks v1] experience tool usage quirks
experience `put` requires a non-empty `id` string; omitting it fails with {"error":"KeyError: 'id'"} even though the schema lists id as optional. Always pass op,id,title,content. Reusing an existing id fully replaces (bumps version). Use op:"search" (query, or empty) to list entries, op:"get" with id to read one, op:"delete" with id to remove.