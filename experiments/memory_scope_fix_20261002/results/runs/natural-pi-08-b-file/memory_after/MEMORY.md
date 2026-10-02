[ledger-sales-total v1] ledger.csv sales total
ledger.csv columns: category,amount. Rows alternate sales/refund. Sales amounts: 10,28,46,64 -> sum 148 (4 rows). export.json gives parser params: utf-8, comma, 0 preamble. "total amount of sales rows" = sum of amount column for category=sales.

[ledger-sales-total v1 v1] ledger.csv sales total
ledger.csv columns: category,amount. Rows alternate sales/refund but values differ per task run — never reuse prior numbers. Procedure: read export.json for parser params (utf-8, comma, preamble_lines as skip_lines), parse_csv, then sum amount (as number) over rows where category == "sales". Verify row count and arithmetic manually.