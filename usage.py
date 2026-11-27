"""Owner-local resource accounting. Not an invoice or subscription system."""
import sqlite3
import math
import secrets
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path

class QuotaExceeded(ValueError):
    pass

def limit_from_env(value):
    if value is None or value=="":
        return None
    if not isinstance(value,str) or not value.isascii() or not value.isdecimal() or len(value)>9:
        raise ValueError("Monthly render seconds must be a nonnegative integer")
    return int(value)

class Ledger:
    def __init__(self, root, limit=None):
        self.path=Path(root)/"usage.sqlite3"
        self.limit=limit
        with closing(self.connect()) as conn, conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS renders (
                id TEXT PRIMARY KEY, project TEXT NOT NULL, month TEXT NOT NULL,
                kind TEXT NOT NULL, seconds INTEGER NOT NULL,
                status TEXT NOT NULL, created TEXT NOT NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS renders_month ON renders(month)")
            # A single private process owns the database. An interrupted job
            # still consumed an attempt; its actual output is unknown.
            conn.execute("UPDATE renders SET status='interrupted' WHERE status='accepted'")

    def connect(self):
        return sqlite3.connect(self.path,timeout=5)

    def effective_limit(self, request_limit=None):
        if request_limit is not None and (type(request_limit) is not int or not 0<=request_limit<=999999999):
            raise ValueError("Invalid request quota")
        limits=[n for n in (self.limit,request_limit) if n is not None]
        return min(limits) if limits else None

    def reserve(self, project, kind, duration, request_limit=None):
        limit=self.effective_limit(request_limit)
        if kind not in {"main","clipper"} or type(duration) not in (int,float) or not math.isfinite(duration) or not 0<duration<=600:
            raise ValueError("Invalid render usage")
        seconds=math.ceil(duration)
        now=datetime.now(timezone.utc)
        month=now.strftime("%Y-%m")
        ident=secrets.token_hex(16)
        with closing(self.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            used=conn.execute("SELECT COALESCE(SUM(seconds),0) FROM renders WHERE month=? AND status!='rejected'",(month,)).fetchone()[0]
            if limit is not None and used+seconds>limit:
                raise QuotaExceeded("Monthly render-attempt quota exceeded")
            conn.execute("INSERT INTO renders VALUES(?,?,?,?,?,?,?)",(ident,project,month,kind,seconds,"accepted",now.isoformat()))
        return ident

    def finish(self, ident, status):
        if status not in {"completed","cancelled","failed","rejected"}:
            raise ValueError("Invalid usage outcome")
        with closing(self.connect()) as conn, conn:
            conn.execute("UPDATE renders SET status=? WHERE id=? AND status='accepted'",(status,ident))

    def summary(self, request_limit=None):
        limit=self.effective_limit(request_limit)
        month=datetime.now(timezone.utc).strftime("%Y-%m")
        with closing(self.connect()) as conn:
            rows=conn.execute("SELECT status,COUNT(*),SUM(seconds) FROM renders WHERE month=? AND status!='rejected' GROUP BY status",(month,)).fetchall()
        outcomes={status:{"attempts":count,"seconds":seconds} for status,count,seconds in rows}
        used=sum(r["seconds"] for r in outcomes.values())
        return {"month":month,"limit_seconds":limit,"attempted_seconds":used,
                "remaining_seconds":None if limit is None else max(0,limit-used),
                "outcomes":outcomes,"unit":"rounded requested output seconds; not a monetary charge"}
