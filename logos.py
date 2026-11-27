"""Single bounded PNG watermark asset; never accept user-supplied file paths."""
import struct
from pathlib import Path
import engine

MAX_BYTES=2*1024*1024
POSITIONS={"top_left","top_right","bottom_left","bottom_right"}

def dimensions(path):
    with Path(path).open("rb") as stream:
        header=stream.read(24)
    if len(header)!=24 or header[:16]!=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
        raise ValueError("PNG image required")
    w,h=struct.unpack(">II",header[16:24])
    if not (1<=w<=1024 and 1<=h<=1024):
        raise ValueError("Logo dimensions must be 1–1024 pixels")
    return w,h

def normalize(source,target):
    dimensions(source)
    engine.run(["ffmpeg","-nostdin","-v","error","-y","-f","image2","-pattern_type","none","-c:v","png","-threads","1","-i",str(source),
                "-map","0:v:0","-frames:v","1","-vf","format=rgba","-c:v","png","-threads","1",str(target)],20)
    dimensions(target)
    if target.stat().st_size>5*1024*1024:
        raise ValueError("Normalized logo too large")

def validate(value,available):
    if value is None:return {"enabled":False,"position":"top_right"}
    if not isinstance(value,dict) or set(value)!={"enabled","position"} or type(value["enabled"]) is not bool or not isinstance(value["position"],str) or value["position"] not in POSITIONS:
        raise ValueError("Invalid logo settings")
    if value["enabled"] and not available:
        raise ValueError("Import a logo first")
    return dict(value)
