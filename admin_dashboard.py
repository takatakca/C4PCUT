"""Standalone, read-only HTML snapshot for a trusted operator. No HTTP service."""
from html import escape
from datetime import datetime, timezone
import os
from pathlib import Path

STYLE = """
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#10101a;color:#f2efff}
body{max-width:1200px;margin:0 auto;padding:28px}h1{font-size:28px;margin:0}
p,small{color:#b6b2ce}header{border-bottom:1px solid #38354a;padding-bottom:18px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:24px 0}
.card,article{background:#1b1929;border:1px solid #39334f;border-radius:12px;padding:16px}
.card strong{display:block;font-size:27px;color:#d8c8ff;margin-top:8px}
section{margin:24px 0}details{margin:12px 0}summary{cursor:pointer;font-weight:600}
article{margin-top:12px}article h3{margin:0 0 8px}.meta{display:flex;gap:20px;flex-wrap:wrap}
progress{width:100%;height:14px;accent-color:#a78bfa}dl{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:12px 0}dd{margin:0}dt{color:#b6b2ce}
.state{color:#d8c8ff;font-weight:600}.inactive{color:#f0c595}
footer{border-top:1px solid #38354a;padding:16px 0;color:#b6b2ce;font-size:13px}
@media(max-width:500px){body{padding:12px}dl{grid-template-columns:1fr}dd{margin-bottom:8px}}
"""
STATES={"active":"Active","expired":"Expired","inactive":"Inactive","missing":"Missing grant","unmapped":"Unmapped","invalid":"Invalid","not_started":"Not started"}
FEATURES={"transcribe":"Transcription","ollama":"Local AI","clipper":"Auto Clipper","music":"Music","animated_captions":"Animated captions","studio_pack":"Studio pack"}

def e(value):
    return escape(str(value),quote=True)

def timestamp(value):
    if value is None:
        return "—"
    try:
        return datetime.fromtimestamp(value,timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError,OverflowError,OSError):
        return "Unavailable"

def usage_html(u):
    if u["status"]!="available":
        return "<p>Usage unavailable — not counted as zero.</p>"
    used=u["attempted_seconds"];limit=u["limit_seconds"]
    if limit is None:
        meter="<p>No configured monthly cap.</p>"
    else:
        ratio=100 if limit==0 else min(100,100*used/limit)
        meter=f'<progress max="100" value="{ratio:.3f}" aria-label="Monthly render usage"></progress><p>{e(u["remaining_seconds"])} seconds remaining of {e(limit)}.</p>'
    outcomes="".join(f"<dt>{e(state)}</dt><dd>{e(item['attempts'])} attempts · {e(item['seconds'])} s</dd>" for state,item in sorted(u["outcomes"].items()))
    return f"<p><strong>{e(used)} seconds attempted</strong></p>{meter}<dl>{outcomes}</dl>"

def workspace_html(row):
    status=row["grant_status"];label=STATES.get(status,"Unknown")
    policy=row["capabilities"]
    features=", ".join(FEATURES.get(x,x) for x in policy["features"]) or "None" if policy else "Not authorized"
    caps=(f"<dl><dt>Maximum edge</dt><dd>{e(policy['max_output_edge'])} px</dd>"
          f"<dt>Maximum render</dt><dd>{e(policy['max_render_seconds'])} s</dd>"
          f"<dt>Project limit</dt><dd>{e(policy['max_projects'])}</dd>"
          f"<dt>Quality</dt><dd>{e(', '.join(policy['qualities']) or 'None')}</dd>"
          f"<dt>Features</dt><dd>{e(features)}</dd></dl>") if policy else "<p>No active capabilities.</p>"
    return (f"<article><h3>{e(row['workspace'])}</h3>"
            f"<div class='meta'><span class='state {'inactive' if status!='active' else ''}'>{e(label)}</span>"
            f"<span>Plan: {e((row['plan'] or '—').upper())}</span><span>Projects: {e(row['projects'])}</span></div>"
            f"<p>Grant expiry: {e(timestamp(row['expires_at']))}</p>{usage_html(row['usage'])}"
            f"<details><summary>Effective capabilities</summary>{caps}</details></article>")

def render_html(report):
    rows=report["workspaces"]
    available=[r for r in rows if r["usage"]["status"]=="available"]
    cards=[("Workspaces",len(rows)),("Active grants",sum(r["grant_status"]=="active" for r in rows)),("Projects",sum(r["projects"] for r in rows)),("Attempted seconds (known)",sum(r["usage"]["attempted_seconds"] for r in available)),("Missing usage",len(rows)-len(available))]
    summary="".join(f"<div class='card'><small>{e(label)}</small><strong>{e(value)}</strong></div>" for label,value in cards)
    groups=[]
    for state in ("active","expired","inactive","not_started","missing","unmapped","invalid"):
        matching=[r for r in rows if r["grant_status"]==state]
        if matching:
            groups.append(f"<details open><summary>{e(STATES[state])} · {len(matching)}</summary>{''.join(workspace_html(r) for r in matching)}</details>")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
            "<meta name='referrer' content='no-referrer'><title>C4PCUT ADMIN</title>"
            f"<style>{STYLE}</style></head><body><header><h1>C4PCUT ADMIN</h1>"
            f"<p>Private read-only snapshot · {e(report['month'])} UTC · Billing disabled</p></header>"
            f"<main><div class='cards'>{summary}</div><section><h2>Workspace status</h2>{''.join(groups)}</section></main>"
            f"<footer>Audit entries: {e(report['audit_entries'])}. Render-attempt seconds are resource accounting, not charges. "
            "Snapshot only; regenerate for current information. Keep this file private.</footer></body></html>")

def write_html(path,report):
    """Create new private file only; never overwrite a report or follow a symlink."""
    path=Path(path)
    if path.suffix.lower()!=".html" or not path.is_absolute():
        raise ValueError("Use a new absolute .html output path")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("Output directory unavailable")
    data=render_html(report).encode("utf-8")
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as out:
        out.write(data)
