"""Bounded, source-time caption editing and output-time mapping."""
import math
import re

MAX_CUES = 500
MAX_TEXT = 400
TIMESTAMP = re.compile(r"^(\d{2}):([0-5]\d):([0-5]\d)[,.](\d{3})$")

def parse_time(s):
    m = TIMESTAMP.fullmatch(s.strip())
    if not m:
        raise ValueError("Invalid subtitle timestamp")
    h, minute, sec, ms = map(int, m.groups())
    return h*3600 + minute*60 + sec + ms/1000

def validate(cues, duration):
    if not isinstance(cues, list) or len(cues) > MAX_CUES:
        raise ValueError("Too many or invalid captions")
    result = []
    for c in cues:
        if not isinstance(c, dict) or set(c) != {"start", "end", "text"}:
            raise ValueError("Invalid caption")
        a, b, text = c["start"], c["end"], c["text"]
        if type(a) not in (int, float) or type(b) not in (int, float) or not (math.isfinite(a) and math.isfinite(b) and 0 <= a < b <= duration + .001):
            raise ValueError("Caption outside video")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            raise ValueError("Invalid caption text")
        if any(ord(ch) < 32 and ch not in "\n\t" for ch in text):
            raise ValueError("Invalid caption characters")
        # Plain text only: avoid interpreting user content as subtitle markup.
        text = text.strip().replace("<", "‹").replace(">", "›").replace("{", "｛").replace("}", "｝").replace("\\", "＼")
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        result.append({"start": a, "end": min(b, duration), "text": text})
    result.sort(key=lambda c: (c["start"], c["end"]))
    return result

def parse_srt(raw, duration):
    if not isinstance(raw, str) or len(raw) > 200000:
        raise ValueError("Subtitle file too large")
    raw = raw.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
    cues = []
    if not raw:
        return cues
    for block in re.split(r"\n[ \t]*\n", raw):
        lines = block.splitlines()
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        if len(lines) < 2 or "-->" not in lines[0]:
            raise ValueError("Invalid SRT cue")
        a, b = lines[0].split("-->", 1)
        cues.append({"start": parse_time(a), "end": parse_time(b), "text": "\n".join(lines[1:])})
    return validate(cues, duration)

def remap(cues, clips):
    """Intersect each caption with the retained clip ranges and shift to output time."""
    result, offset = [], 0.0
    for clip in clips:
        a, b = clip["start"], clip["end"]
        for cue in cues:
            start, end = max(a, cue["start"]), min(b, cue["end"])
            if end - start >= .001:
                result.append({"start": offset + start-a, "end": offset + end-a, "text": cue["text"]})
        offset += b-a
    return result

def stamp(t):
    ms = max(0, round(t*1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def to_srt(cues):
    return "\n".join(f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}\n" for i,c in enumerate(cues,1))


BURN_STYLES = {"classic", "bold", "karaoke"}
CAPTION_MODES = {"soft", *BURN_STYLES}

def validate_mode(mode):
    if not isinstance(mode, str) or mode not in CAPTION_MODES:
        raise ValueError("Unknown subtitle style")
    return mode

def ass_stamp(t):
    cs = max(0, round(t*100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"

def ass_plain(text):
    # No user-supplied override commands or ASS line-break escapes.
    return text.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\r", "").replace("\n", r"\N")

def to_ass(cues, mode):
    """Generate a fixed-style ASS script. Karaoke timings are estimated uniformly."""
    if mode not in BURN_STYLES:
        raise ValueError("Unknown burn-in style")
    size = 27 if mode == "classic" else 36
    primary = "&H0000EFFF" if mode == "karaoke" else "&H00FFFFFF"
    secondary = "&H00FFFFFF"
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 640\nPlayResY: 360\n"
        "ScaledBorderAndShadow: yes\nWrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Main,DejaVu Sans,{size},{primary},{secondary},&H00000000,&H70000000,-1,0,0,0,100,100,0,0,1,3,1,2,36,36,24,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = []
    for cue in cues:
        start, end = round(cue["start"]*100), round(cue["end"]*100)
        if end <= start:
            continue
        text = ass_plain(cue["text"])
        if mode == "karaoke":
            words = cue["text"].split()
            if words:
                span = end-start
                text = " ".join(r"{\kf" + str((i+1)*span//len(words)-i*span//len(words)) + "}" + ass_plain(word) for i,word in enumerate(words))
        events.append(f"Dialogue: 0,{ass_stamp(start/100)},{ass_stamp(end/100)},Main,,0,0,0,,{text}")
    return header + "\n".join(events) + "\n"
