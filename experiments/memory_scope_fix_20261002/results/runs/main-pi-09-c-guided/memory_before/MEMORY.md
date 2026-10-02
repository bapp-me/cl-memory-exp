[count-events-reporting-day v1] Count events in a reporting calendar day (timezone + epoch-seconds store)
Task type: "Count events on reporting calendar day YYYY-MM-DD, using the configured reporting timezone. Return JSON {answer:number}."

Environment observed (deepseek-flash; tools: list_files/read_file/sql over SQLite):
- Workspace contained only reporting.json. Fields: "timezone", "date", "midnight_offset", "next_midnight_offset" (each like "+00:00"), "storage":"UTC epoch seconds", "window":"inclusive start, exclusive next midnight".
- SQLite had one table `events` with columns id INTEGER PK, ts INTEGER (UTC epoch seconds). Discover via `SELECT name FROM sqlite_master WHERE type='table'` and `PRAGMA table_info(events)`.

Procedure that worked:
1. list_files -> read_file reporting.json to get date, offsets, storage, window semantics. Do NOT assume UTC; offsets define the day boundary.
2. Compute boundaries. Day start UTC epoch = epoch_of(local_date 00:00) - midnight_offset. Day end = epoch_of(next_local_date 00:00) - next_midnight_offset. In observed case both offsets +00:00, so start = epoch of date 00:00:00, end = epoch of next day 00:00:00.
   Cheap SQL compute: strftime('%s','YYYY-MM-DD 00:00:00') and strftime('%s', next day '00:00:00').
3. Count with half-open interval: WHERE ts >= start AND ts < end. Also SELECT id,ts,datetime(ts,'unixepoch') ORDER BY ts to eyeball boundary rows.

Observed result: timezone UTC, date 2026-10-11 -> window [1791676800,1791763200). events min=1791673200, max=1791770400, 10 rows total. Boundary rows: ts=1791676800 (2026-10-11 00:00 INCLUDED), ts=1791763200 (2026-10-12 00:00 EXCLUDED). Count=5 (ids 1..5 = 00:00,01:00,02:00,23:00,23:30).

Pitfalls / untested:
- Only observed with zero offset; non-zero midnight_offset handling (subtract offset before comparing) is inferred, not verified.
- Inclusive-start/exclusive-end came from reporting.json "window" and matched data; if "window" absent, event exactly at start included, exactly at next midnight excluded.
- Only single-day requested; multi-day ranges and non-UTC offsets remain untested.