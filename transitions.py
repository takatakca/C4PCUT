"""Duration-preserving visual dip transitions at selected output scene boundaries."""
import math

MODES={"cut","dip_black","dip_white"}
def validate(value):
    if value is None:return {"mode":"cut","seconds":.5}
    if not isinstance(value,dict) or set(value)!={"mode","seconds"} or not isinstance(value["mode"],str) or value["mode"] not in MODES:
        raise ValueError("Invalid transition")
    seconds=value["seconds"]
    if type(seconds) not in (int,float) or not math.isfinite(seconds) or not .2<=seconds<=2:
        raise ValueError("Transition duration must be 0.2–2 seconds")
    return dict(value)

def halves(clips,settings):
    if settings["mode"]=="cut":return [0]*max(0,len(clips)-1)
    durations=[c["end"]-c["start"] for c in clips]
    return [min(settings["seconds"]/2,a/3,b/3) for a,b in zip(durations,durations[1:])]

def filter_for(index,clip,boundaries,settings):
    if settings["mode"]=="cut":return ""
    color="white" if settings["mode"]=="dip_white" else "black"
    duration=clip["end"]-clip["start"]
    before=boundaries[index-1] if index>0 else 0
    after=boundaries[index] if index<len(boundaries) else 0
    filters=""
    if before:filters+=f",fade=t=in:st=0:d={before:.6f}:color={color}"
    if after:filters+=f",fade=t=out:st={duration-after:.6f}:d={after:.6f}:color={color}"
    return filters
