[human-scoped-diagnostic v1] Manually scoped a experience (diagnostic only)
Observed one ledger export: encoding utf-8, delimiter comma, preamble_lines 0; columns category and amount. Those parser settings describe that export only. For each new file read export.json and pass its encoding, delimiter and preamble_lines (as skip_lines) explicitly to parse_csv; verify column names in returned rows, then sum numeric amount where category is sales. Never reuse a prior numeric answer.

[csv-sales-ledger v1] CSV sales ledger parsing (export.json driven)
Task pattern: compute total of sales rows in ledger.csv.
Procedure: read export.json for encoding/delimiter/preamble_lines (skip_lines). One export seen: {"encoding":"utf-8","delimiter":",","preamble_lines":0,"file":"ledger.csv"}; columns category, amount; rows contain sales/refund categories. Pass settings explicitly to parse_csv, confirm column names, then sum numeric amount where category=="sales".
Result of that export: sales amounts 11,29,47,65 => 152. Treat as historical only; never reuse a prior numeric answer.