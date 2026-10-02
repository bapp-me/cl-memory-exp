[reporting-day-event-count v1] Reporting-day event count task pattern
Task type: "Count events on reporting calendar day YYYY-MM-DD, using the configured reporting timezone."

Workspace (list_files) holds reporting.json like:
{"timezone":"UTC","date":"2026-10-11","midnight_offset":"+00:00","next_midnight_offset":"+00:00","storage":"UTC epoch seconds","window":"inclusive start, exclusive next midnight"}
SQLite DB has table `events` (id INTEGER pk, ts INTEGER = UTC epoch seconds).

Procedure:
1. list_files -> read reporting.json to get timezone, midnight_offset, next_midnight_offset, window rule.
2. PRAGMA table_info(events); MIN/MAX(ts), COUNT(*) to see range.
3. Compute window epochs. For UTC use sqlite strftime('%s','YYYY-MM-DD 00:00:00') and strftime('%s','YYYY-MM-DD+1 00:00:00'). For non-UTC, apply midnight_offset to the date's local midnight: start = UTC epoch of local midnight; end = UTC epoch of next local midnight, using next_midnight_offset (may differ due to DST).
4. Count: SELECT COUNT(*) FROM events WHERE ts >= start AND ts < end  (half-open: event exactly at next midnight EXCLUDED; event at start midnight INCLUDED).
5. Verify: list rows with datetime(ts,'unixepoch') to eyeball inclusion.

Pitfall: ts stored in UTC epoch seconds regardless of reporting tz; do NOT treat the date string as UTC unless timezone is UTC. Respect DST offsets.

Return exactly JSON {"answer": <number>}.