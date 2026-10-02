[csv-sales-total-procedure v2] Procedure: sum sales rows from CSV export
Task type: "Compute the total amount of sales rows in the ledger.csv export. Return JSON {answer:number}."
Environment observed: isolated local workspace, tools list_files/read_file/parse_csv/experience. File set seen: ["export.json","ledger.csv"].

Procedure (reusable):
1) list_files to see what exists.
2) If a config/metadata file (e.g. export.json) exists, read it first for parser params: {"encoding":"utf-8","delimiter":",","preamble_lines":0,"file":"ledger.csv"}. Pass these to parse_csv as encoding, delimiter, skip_lines.
3) parse_csv(path) returns {"rows":[{col:val,...}]}; note parse_csv caps at 50 rows (relevant for larger exports).
4) Filter rows where category=="sales", coerce amount to number, sum. Do not confuse with refund rows.
5) Answer as JSON {"answer": <number>}.

Observed instances:
- v1: ledger.csv 92 bytes, UTF-8, comma, 0 preamble. Header category,amount. 8 rows alternating sales/refund. Sales 10,28,46,64 -> sum 148 (count 4).
- v2: same shape/params (export.json utf-8/comma/0 preamble); amounts shift by +1: sales 11,29,47,65 -> sum 152 (count 4). Interpretation "total amount of sales rows" = sum of amount for category=sales. Values changed between runs, so always re-parse rather than reuse prior numbers.
Applicability check: confirm header/rows before assuming column names category/amount and sales/refund values; re-read export.json whenever present since encoding/delimiter/preamble may differ.
Untested: grader expecting row count (4) instead of amount sum; files >50 rows; other delimiters/encodings; refunds subtracted vs excluded.

read_file on a CSV returned a JSON object with bytes + truncated hex prefix (not decoded text), so use parse_csv rather than read_file for row data.
[experience-tool-quirk] experience put requires explicit "id" or fails {"error":"KeyError: 'id'"}; put replaces/creates that entry and bumps version.

[experience-tool-quirk v1] experience tool: put requires explicit id
Observed: calling experience with op=put but omitting "id" failed with {"error":"KeyError: 'id'"}. Retrying with an explicit "id" (e.g. "ledger-sales-total") succeeded: {"saved":"<id>","version":1,"characters":N}. So always pass id on put; put replaces/creates that entry and bumps version. search returns {"matches":[{id,title,content,version}],...}; get by id returns the single entry. Applicability: check applies whenever writing experience entries in this environment. Untested: delete/empty-query behavior.