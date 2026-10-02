[ledger-sales-total v3] CSV ledger aggregation: always read export.json parser params (v3)
Task pattern: "total amount of sales rows in ledger.csv export".

ALWAYS read export.json first — it holds parser params; DO NOT assume defaults (UTF-8/comma/0 preamble). Observed variation: {"encoding":"utf-16","delimiter":"\t","preamble_lines":2,"file":"ledger.csv"}. So call parse_csv(path=file, encoding=export.json.encoding, delimiter=export.json.delimiter, skip_lines=export.json.preamble_lines). Wrong encoding/delimiter silently yields junk or a single column.

ledger.csv columns = category,amount; rows alternate sales/refund. "total amount of sales rows" = SUM(amount) where category=="sales" (a sum, not a row count).

Example run: sales amounts 13,31,49,67 -> 160 (4 rows). (Earlier versions saw 10,28,46,64 -> 148 with a different export; values vary per task, always recompute.)

read_file on a binary/large file returns only a hex prefix + size; prefix_hex ff fe ... indicates UTF-16LE BOM — evidence to confirm encoding.

Always emit the result as {"answer": number}.

[experience-tool-quirks v1] experience tool usage quirks
experience `put` requires a non-empty `id` string; omitting it fails with {"error":"KeyError: 'id'"} even though the schema lists id as optional. Always pass op,id,title,content. Reusing an existing id fully replaces (bumps version). Use op:"search" (query, or empty) to list entries, op:"get" with id to read one, op:"delete" with id to remove.