"""Bounded promotional clip suggestions using observed metadata, not virality claims."""
import math
import engine

DURATIONS = (15, 30, 60)
STYLES = {"clean": "none", "cinematic": "warm", "dynamic": "contrast"}

def suggest(duration, scenes, cues, beats, target, count, style):
    if type(target) is not int or target not in DURATIONS:
        raise ValueError("Choose 15, 30 or 60 seconds")
    if type(count) is not int or not 1 <= count <= 10:
        raise ValueError("Choose one to ten clips")
    if not isinstance(style, str) or style not in STYLES:
        raise ValueError("Unknown clipper style")
    if not math.isfinite(duration) or not 0 < duration <= engine.MAX_DURATION:
        raise ValueError("Invalid source duration")
    length = min(duration, target)
    last = max(0, duration-length)
    step = max(1, length/4)
    # Fixed grid plus observed scene and caption starts. Limit candidates and
    # keep deterministic order; source metadata is already bounded.
    starts = {0.0, last}
    starts.update(min(last, i*step) for i in range(math.ceil(last/step)+1))
    starts.update(min(last,max(0,c["start"])) for c in scenes)
    starts.update(min(last,max(0,c["start"])) for c in cues)
    candidates=[]
    for a in sorted(starts):
        b=a+length
        speech=sum(max(0,min(b,c["end"])-max(a,c["start"])) for c in cues)
        onset_count=sum(a<=t<b for t in beats)
        scene_count=sum(a<c["start"]<b for c in scenes)
        # Speech coverage, transient density and moderate cut density.
        score=2*min(1,speech/length)+min(1,onset_count/length)+.5*min(1,scene_count/max(1,length/4))
        candidates.append((score,a,b,onset_count,scene_count))
    candidates.sort(key=lambda c:(-c[0],c[1]))
    result=[]
    for score,a,b,onsets,scene_count in candidates:
        # Reject near-duplicates; shorter sources can legitimately yield fewer.
        if any(max(0,min(b,c["end"])-max(a,c["start"])) > length*.65+1e-8 for c in result):
            continue
        result.append({"id":len(result),"start":a,"end":b,"duration":length,
                       "score":round(score,3),"onsets":onsets,"scene_count":scene_count,
                       "effect":STYLES[style]})
        if len(result)==count:
            break
    return result

def ranges(candidate, scenes):
    """Preserve source chronology, split at existing boundaries for render effects."""
    a,b=candidate["start"],candidate["end"]
    cuts=[c["start"] for c in scenes if a+.1<c["start"]<b-.1]
    points=[a]+sorted(set(cuts))+[b]
    # Avoid pathological tiny pieces; keep endpoints exact.
    kept=[a]
    for t in points[1:-1]:
        if t-kept[-1]>=.1:
            kept.append(t)
    kept.append(b)
    return [{"start":x,"end":y,"effect":candidate["effect"]} for x,y in zip(kept,kept[1:])]
