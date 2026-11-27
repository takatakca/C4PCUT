"""Offline, read-only C4PCUT pilot administration report. Never served over HTTP."""
import argparse
import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import capabilities
import projects
import workspaces
import studio_gateway

def read_json(path,limit):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>limit:
        raise ValueError("Invalid private configuration")
    with path.open("rb") as stream:
        raw=stream.read(limit+1)
    if len(raw)>limit:
        raise ValueError("Configuration too large")
    return json.loads(raw)

def monthly_usage(folder,month,limit):
    db=folder/"usage.sqlite3"
    if db.is_symlink() or not db.is_file():
        return {"status":"unavailable","limit_seconds":limit}
    try:
        # Unlike Ledger construction, this cannot create a DB or mark jobs interrupted.
        with closing(sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True,timeout=3)) as conn:
            conn.execute("PRAGMA query_only=ON")
            rows=conn.execute("SELECT status,COUNT(*),SUM(seconds) FROM renders WHERE month=? AND status!='rejected' GROUP BY status",(month,)).fetchall()
        outcomes={status:{"attempts":count,"seconds":seconds} for status,count,seconds in rows}
        used=sum(r["seconds"] for r in outcomes.values())
        return {"status":"available","attempted_seconds":used,"limit_seconds":limit,"remaining_seconds":None if limit is None else max(0,limit-used),"outcomes":outcomes}
    except sqlite3.Error:
        return {"status":"unavailable","limit_seconds":limit}

def report(root,workspace_config,mapping,profiles,grants,now=None):
    now=int(time.time()) if now is None else now
    if type(now) is not int or now<0:
        raise ValueError("Invalid report time")
    month=datetime.fromtimestamp(now,timezone.utc).strftime("%Y-%m")
    if not isinstance(workspace_config,dict) or not 1<=len(workspace_config)<=workspaces.MAX_WORKSPACES:
        raise ValueError("Invalid workspace configuration")
    if not isinstance(mapping,dict) or not 1<=len(mapping)<=len(workspace_config):
        raise ValueError("Invalid mapping")
    if any(not isinstance(k,str) or not studio_gateway.UUID.fullmatch(k) or not isinstance(v,str) or v not in workspace_config for k,v in mapping.items()) or len(set(mapping.values()))!=len(mapping):
        raise ValueError("Invalid workspace mapping")
    profiles=capabilities.parse_profiles(profiles)
    if not isinstance(grants,dict) or grants.get("version")!=1 or not isinstance(grants.get("grants"),dict) or not isinstance(grants.get("audit"),list):
        raise ValueError("Invalid private grant registry")
    root=Path(root)/"workspaces"
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid workspace data directory")
    clients={slug:client for client,slug in mapping.items()}
    output=[]
    for slug,record in sorted(workspace_config.items()):
        if not workspaces.SLUG.fullmatch(slug) or slug=="owner" or not isinstance(record,dict):
            raise ValueError("Invalid workspace record")
        local=capabilities.parse(record["capabilities"]) if "capabilities" in record else None
        local_limit=record.get("monthly_render_seconds")
        if local_limit is not None and (type(local_limit) is not int or not 0<=local_limit<=999999999):
            raise ValueError("Invalid workspace quota")
        folder=root/slug
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("Invalid workspace folder")
        client=clients.get(slug)
        grant=grants["grants"].get(client) if client else None
        state="unmapped" if client is None else "missing"
        plan=None
        effective=None
        limit=local_limit
        expiry=None
        if isinstance(grant,dict):
            start,end=grant.get("validFrom"),grant.get("validUntil")
            candidate=grant.get("plan")
            valid=(grant.get("clientId")==client and grant.get("product")=="c4pcut" and isinstance(candidate,str) and candidate in profiles and type(start) is int and type(end) is int and 0<=start<end)
            state="invalid"
            if valid:
                expiry=end
                if grant.get("active") is not True or grant.get("status")!="active":state="inactive"
                elif now<start:state="not_started"
                elif now>=end:state="expired"
                else:
                    state="active";plan=candidate
                    profile=profiles[plan]
                    effective=capabilities.intersect(profile.policy,local).public()
                    limit=min(local_limit,profile.monthly_render_seconds) if local_limit is not None else profile.monthly_render_seconds
        count=sum(1 for p in folder.iterdir() if projects.ID.fullmatch(p.name) and p.is_dir() and not p.is_symlink())
        output.append({"workspace":slug,"grant_status":state,"plan":plan,"expires_at":expiry,"projects":count,"capabilities":effective,"usage":monthly_usage(folder,month,limit)})
    return {"month":month,"mode":"private-pilot-read-only","workspaces":output,"audit_entries":len(grants["audit"]),"billing_enabled":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("data","workspaces","mapping","profiles","grants"):
        p.add_argument("--"+key,required=True,type=Path)
    p.add_argument("--html",type=Path,help="Create a new private HTML snapshot")
    args=p.parse_args()
    try:
        data=report(args.data,read_json(args.workspaces,32768),read_json(args.mapping,16384),read_json(args.profiles,32768),read_json(args.grants,262144))
        if args.html:
            from admin_dashboard import write_html
            write_html(args.html,data)
            print("Private HTML snapshot created. Keep it outside public web directories.")
        else:
            print(json.dumps(data,indent=2))
    except (ValueError,OSError,TypeError):
        p.exit(1,"Report unavailable: invalid or missing private data\n")

if __name__=="__main__":
    main()
