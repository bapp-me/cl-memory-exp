[ledger-sales-total v1] ledger.csv sales total
ledger.csv columns: category,amount. Rows alternate sales/refund. Sales amounts: 10,28,46,64 -> sum 148 (4 rows). export.json gives parser params: utf-8, comma, 0 preamble. "total amount of sales rows" = sum of amount column for category=sales.

[ledger-sales-total v1 v1] ledger.csv sales total (export.json driven)
ledger.csv sales total task.
ALWAYS read export.json next to the CSV first: it holds encoding, delimiter, preamble_lines.
This variant: encoding=utf-16 (UTF-16LE with BOM), delimiter=TAB (\t), preamble_lines=2.
Parsing with default comma delimiter produced a single garbage "category\tamount" key -> wrong. Must use tab delimiter.
Data (after 2 skipped preamble lines; header row category/amount): sales 12,30,48,66 sum=156; refunds 21,39,57,75.
"total amount of sales rows" = sum of amount where category=sales = 156.
Lesson: never assume comma/utf-8; check export.json (or sibling config) for parser params.