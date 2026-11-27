"""Single bounded PNG watermark asset; never accept user-supplied file paths."""
import struct
import math
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

def validate(value,available,duration=600):
    default={"enabled":False,"position":"top_right","size":20,"opacity":1,"start":0,"end":None}
    if value is None:return default
    if not isinstance(value,dict) or not {"enabled","position"}<=set(value) or set(value)-set(default) or type(value["enabled"]) is not bool or not isinstance(value["position"],str) or value["position"] not in POSITIONS:
        raise ValueError("Invalid logo settings")
    result={**default,**value}
    size,opacity,a,b=(result[k] for k in ("size","opacity","start","end"))
    if type(size) is not int or not 10<=size<=40 or type(opacity) not in (int,float) or not math.isfinite(opacity) or not .1<=opacity<=1:
        raise ValueError("Invalid logo size or opacity")
    if type(a) not in (int,float) or not math.isfinite(a) or not 0<=a<duration:
        raise ValueError("Invalid logo start")
    if b is not None and (type(b) not in (int,float) or not math.isfinite(b) or not a<b<=duration+.000001):
        raise ValueError("Invalid logo end")
    if result["enabled"] and not available:raise ValueError("Import a logo first")
    return result
