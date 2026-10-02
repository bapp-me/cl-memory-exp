"""Read-only, logged SQLite interface; the Agent never receives gold data."""
from __future__ import annotations
import argparse
from pathlib import Path
from mcp.server.fastmcp import FastMCP

parser = argparse.ArgumentParser()
parser.add_argument('--db', required=True)
parser.add_argument('--log', required=True)
args = parser.parse_args()
db_path = Path(args.db).resolve()
log_path = Path(args.log).resolve()
log_path.parent.mkdir(parents=True, exist_ok=True)
mcp = FastMCP('sql')


@mcp.tool()
def query(sql: str) -> dict:
    """Execute one read-only SQLite query to inspect schema/data or calculate an answer.

    sqlite_master and schema PRAGMAs are available. At most 50 rows are returned;
    use aggregation or LIMIT for large outputs. SQL errors are returned for repair.
    """
    from sql_backend import execute_query
    return execute_query(sql, db_path, log_path)


if __name__ == '__main__':
    mcp.run(transport='stdio')
