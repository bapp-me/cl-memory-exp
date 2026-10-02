[ledger-sales-total v4] CSV ledger aggregation pattern (read export.json params first)
Task pattern: "total amount of sales rows in ledger.csv export".
Steps: ALWAYS read export.json first — it holds parser params (encoding, delimiter, preamble_lines, file). Do not assume UTF-8/comma/no-preamble: seen cases with {"encoding":"utf-16","delimiter":"\t","preamble_lines":2}.
Call parse_csv(path, encoding=export.encoding, delimiter=export.delimiter, skip_lines=export.preamble_lines). Note: a raw tab in JSON makes the parser emit "\t" which fails with TypeError "delimiter must be a 1-character string" — pass delimiter as the two-character escape "\t" (backslash-t) so it decodes to a real tab.
ledger.csv columns = category,amount; rows alternate sales/refund. "total amount of sales rows" = SUM(amount) over rows where category=="sales" (a sum, not a row count). Example: sales 13,31,49,67 -> 160. Amounts may be strings in the raw rows; cast/round to number.
Always emit result as {"answer": number}.

[experience-tool-quirks v1] experience tool usage quirks
experience `put` requires a non-empty `id` string; omitting it fails with {"error":"KeyError: 'id'"} even though the schema lists id as optional. Always pass op,id,title,content. Reusing an existing id fully replaces (bumps version). Use op:"search" (query, or empty) to list entries, op:"get" with id to read one, op:"delete" with id to remove.