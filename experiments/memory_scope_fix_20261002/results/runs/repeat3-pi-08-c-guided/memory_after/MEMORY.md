[csv-sales-total-procedure v2] Procedure: sum sales rows from CSV export
Task type: "Compute the total amount of sales rows in the ledger.csv export. Return JSON {answer:number}."
Environment: isolated workspace, tools list_files/read_file/parse_csv/experience. Files seen: ["export.json","ledger.csv"].

Procedure (reusable):
1) list_files first.
2) ALWAYS read export.json first when present — parser params vary per task. Seen so far: {"encoding":"utf-8","delimiter":",","preamble_lines":0,"file":"ledger.csv"}; and {"encoding":"utf-16","delimiter":"\t","preamble_lines":2,"file":"ledger.csv"}. Pass as parse_csv(path, encoding=..., delimiter=..., skip_lines=preamble_lines). Note JSON "\t" must be passed as an actual tab char.
3) parse_csv returns {"rows":[{col:val,...}]} with string values; caps at 50 rows.
4) Confirm header/values, filter rows where category=="sales", coerce amount to number, sum. Exclude refund rows (do not subtract).
5) Answer JSON {"answer": <number>}.

Observed instances: utf-8/comma/0 preamble: sales 10,28,46,64 -> 148 (count 4). utf-16/tab/2 preamble: sales 12,30,48,66 -> 156 (count 4). Both cases alternating sales/refund, 8 rows.
Untested: grader expecting count vs sum (assumed sum per "total amount"); files >50 rows; refunds subtracted vs excluded.
read_file on a CSV returned bytes + truncated hex prefix, so use parse_csv not read_file for rows.

[experience-tool-quirk v1] experience tool: put requires explicit id
Observed: calling experience with op=put but omitting "id" failed with {"error":"KeyError: 'id'"}. Retrying with an explicit "id" (e.g. "ledger-sales-total") succeeded: {"saved":"<id>","version":1,"characters":N}. So always pass id on put; put replaces/creates that entry and bumps version. search returns {"matches":[{id,title,content,version}],...}; get by id returns the single entry. Applicability: check applies whenever writing experience entries in this environment. Untested: delete/empty-query behavior.