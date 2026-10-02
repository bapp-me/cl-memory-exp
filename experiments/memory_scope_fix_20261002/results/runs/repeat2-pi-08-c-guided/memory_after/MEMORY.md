[csv-sales-total-procedure v2] Procedure: sum sales rows from CSV export
Task type: "Compute the total amount of sales rows in the ledger.csv export. Return JSON {answer:number}."
Environment: isolated local workspace, tools list_files/read_file/parse_csv/experience. File set seen: ["export.json","ledger.csv"].

Procedure (reusable):
1) list_files to see what exists.
2) ALWAYS read export.json first for parser params (encoding/delimiter/preamble_lines/file). Params VARY between instances: seen utf-8/comma/0 (preamble 0) AND utf-16/tab/2. Pass them to parse_csv as encoding, delimiter, skip_lines.
3) parse_csv returns {"rows":[{col:val,...}]}; caps at 50 rows (relevant for larger exports).
4) Filter rows where category=="sales", coerce amount to number, sum. Do not include refund rows. Values arrive as strings.
5) Answer JSON {"answer": <number>}.

Observed instances:
- utf-8/comma/0 preamble: header category,amount; 8 rows alternating sales(10,28,46,64)/refund -> sum 148 (count 4).
- utf-16/tab/2 preamble: 8 rows alternating sales(12,30,48,66)/refund -> sum 156 (count 4).
Interpretation: "total amount of sales rows" = sum of amount for category==sales. Untested alternative: row count. Untested: files >50 rows, refunds subtracted vs excluded.

read_file on CSV returns JSON with bytes + truncated hex prefix (not decoded text) -> use parse_csv for row data, despite the utf-16 file appearing readable.

[experience-tool-quirk v1] experience tool: put requires explicit id
Observed: calling experience with op=put but omitting "id" failed with {"error":"KeyError: 'id'"}. Retrying with an explicit "id" (e.g. "ledger-sales-total") succeeded: {"saved":"<id>","version":1,"characters":N}. So always pass id on put; put replaces/creates that entry and bumps version. search returns {"matches":[{id,title,content,version}],...}; get by id returns the single entry. Applicability: check applies whenever writing experience entries in this environment. Untested: delete/empty-query behavior.