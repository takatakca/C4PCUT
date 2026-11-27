"""Bounded output-time title layer, independent of source-time captions."""
import math
import captions

MAX_TITLES=12
MAX_TEXT=120
POSITIONS={"top":8,"center":5}

def validate(items,duration):
    if not isinstance(items,list) or len(items)>MAX_TITLES:
        raise ValueError("Invalid title list")
    result=[]
    for item in items:
        if not isinstance(item,dict) or set(item)!={"start","end","text","position"}:
            raise ValueError("Invalid title fields")
        a,b,text,pos=(item[k] for k in ("start","end","text","position"))
        if type(a) not in (int,float) or type(b) not in (int,float) or not (math.isfinite(a) and math.isfinite(b) and 0<=a<b<=duration+.000001 and b-a>=.1-.000001):
            raise ValueError("Invalid title duration")
        if not isinstance(text,str) or not text.strip() or len(text)>MAX_TEXT or any(ord(ch)<32 or ord(ch)==127 for ch in text):
            raise ValueError("Invalid title text")
        if not isinstance(pos,str) or pos not in POSITIONS:
            raise ValueError("Invalid title position")
        text=text.strip().replace("{","｛").replace("}","｝").replace("\\","＼").replace("<","‹").replace(">","›")
        result.append({"start":a,"end":min(b,duration),"text":text,"position":pos})
    result.sort(key=lambda x:(x["start"],x["end"]))
    for left,right in zip(result,result[1:]):
        if left["end"]>right["start"]+1e-9:
            raise ValueError("Titles must not overlap")
    return result

def for_output(items,duration):
    """Titles stay anchored to edited time; shortening clips truncates/hides titles."""
    return [{**item,"end":min(item["end"],duration)} for item in items
            if min(item["end"],duration)-item["start"]>=.01]

def to_ass(items):
    header=("[Script Info]\nScriptType: v4.00+\nPlayResX: 640\nPlayResY: 360\n"
            "ScaledBorderAndShadow: yes\nWrapStyle: 0\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
    for pos,alignment in POSITIONS.items():
        header+=f"Style: {pos},DejaVu Sans,34,&H00FFFFFF,&H00FFFFFF,&H00000000,&H70000000,-1,0,0,0,100,100,0,0,1,3,1,{alignment},30,30,24,1\n"
    header+="\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    return header+"\n".join(f"Dialogue: 0,{captions.ass_stamp(t['start'])},{captions.ass_stamp(t['end'])},{t['position']},,0,0,0,,{captions.ass_plain(t['text'])}" for t in items)+"\n"
