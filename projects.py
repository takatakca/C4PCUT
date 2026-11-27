"""Private single-user saved projects, using bounded manifests and fixed paths."""
import json
import math
import os
import re
import shutil
import secrets
from pathlib import Path
import engine
import captions
import titles
import logos
import music
import studio_pack

ID = re.compile(r"[a-f0-9]{32}")
MAX_PROJECTS = 8
MAX_MANIFEST = 262144
MIMES = {"mp4":"video/mp4","mov":"video/quicktime","webm":"video/webm","m4v":"video/mp4"}

def clean_name(name):
    if not isinstance(name,str) or not name.strip() or len(name)>160 or any(ord(c)<32 for c in name):
        raise ValueError("Invalid project name")
    return name.strip()

def validate_segments(clips, duration):
    if not isinstance(clips,list) or len(clips)>engine.MAX_CLIPS:
        raise ValueError("Invalid scenes")
    last=0
    for i,c in enumerate(clips):
        if not isinstance(c,dict) or set(c)!={"id","start","end"} or type(c["id"]) is not int or c["id"]!=i:
            raise ValueError("Invalid scene")
        a,b=c["start"],c["end"]
        if any(type(x) not in (float,int) or not math.isfinite(x) for x in (a,b)) or abs(a-last)>1e-6 or not a<b<=duration+1e-6:
            raise ValueError("Invalid scene boundaries")
        last=b
    if clips and abs(last-duration)>1e-6:
        raise ValueError("Incomplete scene coverage")
    return clips

def validate_state(payload, clips, metadata, has_music, has_logo=False):
    name=clean_name(payload.get("name"))
    selected=payload.get("selected",[])
    edits=payload.get("edits",{})
    if not isinstance(selected,list) or not isinstance(edits,dict):
        raise ValueError("Invalid saved selection")
    # Validate every edit even when its scene is not selected.
    if clips:
        engine.validate_edits(list(range(len(clips))),clips,edits)
        if selected:
            engine.validate_selection(selected,clips)
    elif selected or edits:
        raise ValueError("No scenes available")
    order=engine.validate_order(selected,payload.get("order"))
    use_music=payload.get("use_music",False)
    if type(use_music) is not bool or (use_music and not has_music):
        raise ValueError("Invalid music state")
    preset,framing=payload.get("preset","original"),payload.get("framing","fit")
    engine.validate_format(preset,framing)
    quality=payload.get("quality","standard")
    engine.validate_quality(quality)
    mime=payload.get("source_mime","video/mp4")
    if not isinstance(mime,str) or mime not in set(MIMES.values()) | {""}:
        raise ValueError("Invalid source MIME")
    brief=payload.get("studio_brief")
    if brief is not None:
        brief=studio_pack.parse_brief(brief)
    return {"name":name,"selected":selected,"order":order,"edits":edits,"source_mime":mime,"studio_brief":brief,
            "cues":captions.validate(payload.get("cues",[]),metadata["duration"]),
            "titles":titles.validate(payload.get("titles",[]),metadata["duration"]),
            "logo":logos.validate(payload.get("logo"),has_logo,metadata["duration"]),
            "caption_mode":captions.validate_mode(payload.get("caption_mode","soft")),
            "use_music":use_music,"music_gain":music.validate_gain(payload.get("music_gain",.35)),
            "source_gain":music.validate_gain(payload.get("source_gain",1)),
            "preset":preset,"framing":framing,"quality":quality}

def save(job, payload):
    folder=job["folder"]
    clips=validate_segments(job.get("clips",[]),job["metadata"]["duration"])
    state=validate_state(payload,clips,job["metadata"],(folder/"music.wav").is_file(),(folder/"logo.png").is_file())
    # Immutable soundtrack copy per saved revision. The current working
    # soundtrack can be replaced without changing the prior saved revision.
    revision=secrets.token_hex(16) if (folder/"music.wav").is_file() else None
    logo_revision=secrets.token_hex(16) if (folder/"logo.png").is_file() else None
    manifest={"logo_revision":logo_revision,"version":1,"metadata":job["metadata"],"clips":clips,"state":state,"music_revision":revision}
    raw=json.dumps(manifest,ensure_ascii=False,allow_nan=False).encode("utf-8")
    if len(raw)>MAX_MANIFEST:
        raise ValueError("Project manifest too large")
    tmp=folder/"project.pending"
    try:
        if revision:
            shutil.copyfile(folder/"music.wav",folder/f"saved-{revision}.wav")
        if logo_revision:
            shutil.copyfile(folder/"logo.png",folder/f"saved-logo-{logo_revision}.png")
        with tmp.open("wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        tmp.replace(folder/"project.json")
    except Exception:
        tmp.unlink(missing_ok=True)
        if revision:
            (folder/f"saved-{revision}.wav").unlink(missing_ok=True)
        if logo_revision:
            (folder/f"saved-logo-{logo_revision}.png").unlink(missing_ok=True)
        raise
    for old in folder.glob("saved-logo-*.png"):
        if old.name!=f"saved-logo-{logo_revision}.png":old.unlink(missing_ok=True)
    for old in folder.glob("saved-*.wav"):
        if old.name!=f"saved-{revision}.wav":
            old.unlink(missing_ok=True)
    return state

def read(folder):
    path=folder/"project.json"
    if not path.is_file() or path.stat().st_size>MAX_MANIFEST or not (folder/"source.media").is_file():
        raise ValueError("Missing or invalid saved project")
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("version")!=1:
        raise ValueError("Unsupported project version")
    meta=data["metadata"]
    duration=meta["duration"]
    if type(duration) not in (int,float) or not math.isfinite(duration) or not 0<duration<=engine.MAX_DURATION:
        raise ValueError("Invalid project duration")
    clips=validate_segments(data["clips"],duration)
    revision=data.get("music_revision")
    if revision is not None and (not isinstance(revision,str) or not ID.fullmatch(revision) or not (folder/f"saved-{revision}.wav").is_file()):
        raise ValueError("Missing saved soundtrack")
    logo_revision=data.get("logo_revision")
    if logo_revision is not None and (not isinstance(logo_revision,str) or not ID.fullmatch(logo_revision) or not (folder/f"saved-logo-{logo_revision}.png").is_file()):
        raise ValueError("Missing saved logo")
    data["state"]=validate_state(data["state"],clips,meta,revision is not None,logo_revision is not None)
    return data

def restore(folder):
    data=read(folder)
    revision=data["music_revision"]
    track=folder/"music.wav"
    result={"folder":folder,"metadata":data["metadata"],"clips":data["clips"]}
    if revision:
        tmp=folder/"restore-music.pending"
        try:
            shutil.copyfile(folder/f"saved-{revision}.wav",tmp)
            analysis=music.analyze(tmp,data["metadata"]["duration"])
            tmp.replace(track)
            result["music_analysis"]=analysis
        finally:
            tmp.unlink(missing_ok=True)
    else:
        track.unlink(missing_ok=True)
    logo_revision=data.get("logo_revision")
    logo=folder/"logo.png"
    if logo_revision:
        tmp=folder/"restore-logo.pending"
        try:
            shutil.copyfile(folder/f"saved-logo-{logo_revision}.png",tmp)
            logos.dimensions(tmp)
            tmp.replace(logo)
        finally:tmp.unlink(missing_ok=True)
    else:logo.unlink(missing_ok=True)
    return result,data["state"]

def list_saved(root):
    result=[]
    for folder in sorted(root.iterdir()):
        if not ID.fullmatch(folder.name) or not folder.is_dir() or folder.is_symlink():
            continue
        try:
            data=read(folder)
            result.append({"id":folder.name,"name":data["state"]["name"],"duration":data["metadata"]["duration"],"saved":True})
        except (OSError,ValueError,KeyError,TypeError):
            result.append({"id":folder.name,"name":"Unsaved or unreadable import "+folder.name[:8],"duration":None,"saved":False})
    return result
