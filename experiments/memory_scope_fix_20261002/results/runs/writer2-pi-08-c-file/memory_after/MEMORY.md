[csv-ledger-parsing v1] CSV ledger parsing: read_file returns hex, use parse_csv; export.json holds parser params
Workspace task pattern (CSV export analysis tasks):
- list_files first to see what exists. Often there's a data file (e.g. ledger.csv) plus a config file (export.json).
- read_file on a CSV/binary returns ONLY {"path","bytes","prefix_hex"} — a hex byte prefix, NOT the text. Don't decode the whole file from prefix_hex; it may be truncated. Use parse_csv instead to get all rows.
- export.json typically specifies parser parameters for the data file: {"encoding":"utf-8","delimiter":",","preamble_lines":0,"file":"ledger.csv"}. Pass these to parse_csv: path, encoding, delimiter, skip_lines (== preamble_lines).
- parse_csv returns {"rows":[{col:value,...}]} with values as STRINGS; cast to int/float before math.
- Example: 8 rows alternating category sales/refund, amounts 10,19,28,37,46,55,64,73. "total amount of sales rows" = sum amounts where category=="sales" = 10+28+46+64 = 148. Ambiguity: "total amount" meant summed monetary amount, not row count (count of sales rows = 4). For phrasing "total amount ... of X rows" prefer summing the value column.
- Return final answer as JSON {"answer": number}.