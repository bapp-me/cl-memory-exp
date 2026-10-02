"""Shared read-only SQLite semantics for Claude MCP and Hermes custom tool."""
import json
import sqlite3
import time
from pathlib import Path


def execute_query(sql: str, db_path: Path, log_path: Path) -> dict:
    started=time.monotonic()
    con=sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro',uri=True,timeout=20)
    con.execute('PRAGMA query_only=ON')
    forbidden={sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH,sqlite3.SQLITE_INSERT,
               sqlite3.SQLITE_UPDATE,sqlite3.SQLITE_DELETE,sqlite3.SQLITE_CREATE_TABLE,
               sqlite3.SQLITE_DROP_TABLE,sqlite3.SQLITE_ALTER_TABLE}
    safe_pragmas={'table_info','table_xinfo','index_list','index_info','foreign_key_list','schema_version'}
    def authorize(action,arg1,arg2,database,source):
        if action in forbidden or (action==sqlite3.SQLITE_PRAGMA and str(arg1).lower() not in safe_pragmas):return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    con.set_authorizer(authorize)
    con.set_progress_handler(lambda:int(time.monotonic()-started>30),10000)
    try:
        cur=con.execute(sql);rows=cur.fetchmany(51)
        out={'columns':[x[0] for x in (cur.description or [])],'rows':rows[:50],'truncated':len(rows)>50}
        for row in out['rows']:
            if any(isinstance(x,bytes) for x in row):raise ValueError('Binary values are not supported')
        out['rows']=[[x[:1800]+'[cell truncated]' if isinstance(x,str) and len(x)>1800 else x for x in r] for r in out['rows']]
    except (sqlite3.Error,ValueError) as error:out={'error':str(error)}
    finally:con.close()
    log_path.parent.mkdir(parents=True,exist_ok=True)
    with log_path.open('a',encoding='utf-8') as f:
        f.write(json.dumps({'sql':sql,'result':out,'seconds':round(time.monotonic()-started,4)},ensure_ascii=False)+'\n')
    return out
