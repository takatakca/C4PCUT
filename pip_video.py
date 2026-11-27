"""Bounded secondary-video normalization. Private files only, no arbitrary URLs."""
import math
from pathlib import Path
import engine

MAX_BYTES=24*1024*1024
MAX_SECONDS=30
POSITIONS={"top_left","top_right","bottom_left","bottom_right"}

def normalize(source,target):
    source,target=Path(source),Path(target)
    if source.is_symlink() or not source.is_file() or not 0<source.stat().st_size<=MAX_BYTES:
        raise ValueError("Invalid secondary video size")
    with source.open("rb") as stream:
        header=stream.read(12)
    if len(header)!=12 or header[4:8]!=b"ftyp":
        raise ValueError("MP4 secondary video required")
    # Force the local MP4 demuxer and forbid network protocols.
    import json
    result=json.loads(engine.run(["ffprobe","-v","error","-protocol_whitelist","file,pipe","-f","mov","-show_format","-show_streams","-of","json",str(source)],20).stdout)
    video=next((s for s in result["streams"] if s["codec_type"]=="video" and not s.get("disposition",{}).get("attached_pic")),None)
    duration=float(result["format"]["duration"])
    if video is None or not math.isfinite(duration) or not .1<=duration<=MAX_SECONDS or not 2<=video["width"]<=1920 or not 2<=video["height"]<=1920:
        raise ValueError("Secondary video must be 0.1–30 seconds and at most 1920 pixels per edge")
    engine.run(["ffmpeg","-nostdin","-v","error","-y","-protocol_whitelist","file,pipe","-f","mov","-threads","2","-i",str(source),
                "-map","0:"+str(video["index"]),"-an","-sn","-dn","-t",str(MAX_SECONDS),
                "-vf","scale=720:720:force_original_aspect_ratio=decrease:force_divisible_by=2,fps=30,setsar=1",
                "-c:v","libx264","-threads","2","-preset","veryfast","-crf","25","-pix_fmt","yuv420p","-movflags","+faststart","-f","mp4",str(target)],90)
    meta=engine.probe(target)
    if meta["audio"] or max(meta["width"],meta["height"])>720 or not .1<=meta["duration"]<=MAX_SECONDS+.04 or target.stat().st_size>MAX_BYTES:
        raise ValueError("Invalid normalized secondary video")
    return meta

def validate(value,available,duration=600):
    default={"enabled":False,"position":"bottom_right","size":30,"start":0,"source_in":0,"length":1}
    if value is None:return default
    if not isinstance(value,dict) or set(value)-set(default) or not {"enabled","position"}<=set(value):
        raise ValueError("Invalid picture-in-picture settings")
    result={**default,**value}
    if type(result["enabled"]) is not bool or not isinstance(result["position"],str) or result["position"] not in POSITIONS or type(result["size"]) is not int or not 15<=result["size"]<=50:
        raise ValueError("Invalid picture-in-picture appearance")
    a,s,l=(result[k] for k in ("start","source_in","length"))
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (a,s,l)) or not 0<=a<duration or not 0<=s<MAX_SECONDS or not .1<=l<=MAX_SECONDS or s+l>MAX_SECONDS+.000001:
        raise ValueError("Invalid picture-in-picture interval")
    if result["enabled"]:
        if not isinstance(available,dict) or s+l>available["duration"]+.000001:
            raise ValueError("Secondary video missing or trim exceeds its duration")
    return result
