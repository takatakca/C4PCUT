#!/usr/bin/env python3
"""Offline administrative grant registry. Linux owner shell only, not an HTTP API."""
import argparse
import fcntl
import json
import os
import re
import tempfile
import time
from pathlib import Path

UUID=re.compile(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}")
PLANS={"free","standard","pro"}
MAX_GRANTS=500
MAX_AUDIT=1000
MAX_BYTES=262144

def read_registry(path):
    if not path.exists():
        return {"version":1,"grants":{},"audit":[]}
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_BYTES:
        raise ValueError("Invalid private registry file")
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict) or data.get("version")!=1 or not isinstance(data.get("grants"),dict) or not isinstance(data.get("audit"),list):
        raise ValueError("Invalid registry schema")
    return data

def change(path,client,action,plan=None,until=None,now=None):
    if not isinstance(client,str) or not UUID.fullmatch(client):
        raise ValueError("Invalid client UUID")
    now=int(time.time()) if now is None else now
    if type(now) is not int or now<0:
        raise ValueError("Invalid time")
    if action=="grant":
        if plan not in PLANS or type(until) is not int or not now<until<=now+366*86400:
            raise ValueError("Choose a known plan and expiry within 366 days")
    elif action!="revoke":
        raise ValueError("Invalid action")
    path=Path(path)
    if not path.is_absolute() or not path.parent.is_dir():
        raise ValueError("Use an absolute path in an existing private directory")
    if path.is_symlink():
        raise ValueError("Registry symlink forbidden")
    # Single trusted operator directory, shared lock across CLI processes.
    lock_path=path.with_name(path.name+".lock")
    fd=os.open(lock_path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"r+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        data=read_registry(path)
        rows=data["grants"]
        old=rows.get(client)
        if action=="grant":
            if client not in rows and len(rows)>=MAX_GRANTS:
                raise ValueError("Registry capacity reached")
            row={"clientId":client,"product":"c4pcut","active":True,"plan":plan,"status":"active","validFrom":now,"validUntil":until}
        else:
            if not isinstance(old,dict):
                raise ValueError("Unknown grant")
            row={**old,"active":False,"status":"revoked"}
        if len(data["audit"])>=MAX_AUDIT:
            raise ValueError("Audit capacity reached; archive and review offline before further changes")
        rows[client]=row
        data["audit"].append({"at":now,"action":action,"clientId":client,"before":old,"after":row})
        raw=json.dumps(data,separators=(",",":"),ensure_ascii=True).encode()
        if len(raw)>MAX_BYTES:
            raise ValueError("Registry capacity reached; archive offline")
        temp=None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent,prefix=".grant-",delete=False) as out:
                temp=Path(out.name)
                os.fchmod(out.fileno(),0o600)
                out.write(raw)
                out.flush()
                os.fsync(out.fileno())
            temp.replace(path)
            dirfd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(dirfd)
            finally:os.close(dirfd)
        finally:
            if temp:temp.unlink(missing_ok=True)
    return row

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry",required=True,type=Path)
    parser.add_argument("--client",required=True)
    parser.add_argument("action",choices=("grant","revoke"))
    parser.add_argument("--plan",choices=sorted(PLANS))
    parser.add_argument("--until",type=int,help="UTC epoch seconds")
    args=parser.parse_args()
    try:
        if args.action=="revoke" and (args.plan is not None or args.until is not None):
            raise ValueError("Revoke takes no plan or expiry")
        change(args.registry,args.client,args.action,args.plan,args.until)
    except (ValueError,OSError) as exc:
        parser.exit(1,f"Grant change refused: {exc}\n")
    print("Private access grant updated; no payment or invoice created.")

if __name__=="__main__":
    main()
