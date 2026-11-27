"""Trusted, bounded FFmpeg operations for local development."""
import json
import math
import re
import subprocess
from pathlib import Path

MAX_DURATION = 600
MAX_CLIPS = 60
MAX_BYTES = 250 * 1024 * 1024

def run(args, timeout=180):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout)

def probe(path):
    info = json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], 30).stdout)
    duration = float(info["format"]["duration"])
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if not video or not math.isfinite(duration) or not 0 < duration <= MAX_DURATION:
        raise ValueError("Requires a video of 10 minutes or less")
    if video["width"] > 4096 or video["height"] > 4096:
        raise ValueError("Maximum input dimension is 4096 pixels")
    return {"duration": duration, "width": video["width"], "height": video["height"],
            "audio": any(s["codec_type"] == "audio" for s in info["streams"])}

def segments(duration, cuts):
    points = [0.0]
    for t in sorted(set(cuts)):
        if math.isfinite(t) and t - points[-1] >= 0.35 and duration - t >= 0.35 and len(points) < MAX_CLIPS:
            points.append(t)
    points.append(duration)
    return [{"id": i, "start": a, "end": b} for i, (a, b) in enumerate(zip(points, points[1:]))]

def analyze(path, metadata):
    result = run(["ffmpeg", "-nostdin", "-hide_banner", "-threads", "2", "-filter_threads", "2",
                  "-i", str(path), "-an", "-vf", "scale=480:-2,select='gt(scene,0.32)',showinfo",
                  "-f", "null", "-"])
    cuts = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", result.stderr)]
    return segments(metadata["duration"], cuts)

def validate_selection(ids, clips):
    if not isinstance(ids, list) or not ids or len(ids) > MAX_CLIPS or any(type(i) is not int for i in ids):
        raise ValueError("Select at least one valid clip")
    if len(set(ids)) != len(ids) or any(i < 0 or i >= len(clips) for i in ids):
        raise ValueError("Invalid clip selection")
    return [clips[i] for i in sorted(ids)]

EFFECTS = {"none": "", "mono": ",hue=s=0", "warm": ",colorbalance=rs=.06:bs=-.05", "contrast": ",eq=contrast=1.15:saturation=1.10"}

def validate_edits(ids, clips, edits):
    selected = validate_selection(ids, clips)
    if not isinstance(edits, dict) or len(edits) > MAX_CLIPS:
        raise ValueError("Invalid edits")
    known = {str(c["id"]): c for c in clips}
    if any(k not in known for k in edits):
        raise ValueError("Unknown scene")
    validated = {}
    for key, item in edits.items():
        base = known[key]
        if not isinstance(item, dict) or set(item) - {"start", "end", "effect"}:
            raise ValueError("Invalid edit")
        a, b = item.get("start", base["start"]), item.get("end", base["end"])
        effect = item.get("effect", "none")
        if type(a) not in (int, float) or type(b) not in (int, float):
            raise ValueError("Invalid trim")
        if not (math.isfinite(a) and math.isfinite(b) and base["start"] <= a < b <= base["end"]):
            raise ValueError("Trim outside scene")
        if b-a < min(.1, base["end"]-base["start"]) - 1e-9:
            raise ValueError("Trim too short")
        if not isinstance(effect, str) or effect not in EFFECTS:
            raise ValueError("Unknown effect")
        validated[key] = {**base, "start": a, "end": b, "effect": effect}
    return [validated.get(str(c["id"]), c) for c in selected]

def render(source, output, clips, audio, subtitle_path=None, music_path=None, music_gain=.35, source_gain=1):
    # Normalize timestamps and concatenate independently trimmed video/audio streams.
    filters, inputs = [], []
    music_index = 2 if subtitle_path is not None else 1
    has_audio = audio or music_path is not None
    for i, c in enumerate(clips):
        a, b = c["start"], c["end"]
        filters.append(f"[0:v:0]trim=start={a}:end={b},setpts=PTS-STARTPTS,scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1{EFFECTS[c.get('effect', 'none')]}[v{i}]")
        inputs.append(f"[v{i}]")
        if music_path is not None:
            duration = b-a
            # Music is anchored to source time; excluded footage removes
            # the corresponding music interval. Pad short tracks with silence.
            filters.append(f"[{music_index}:a:0]apad=whole_dur={b},atrim=start={a}:end={b},asetpts=PTS-STARTPTS,volume={music_gain}[m{i}]")
            if audio:
                filters.append(f"[0:a:0]apad=whole_dur={b},atrim=start={a}:end={b},asetpts=PTS-STARTPTS,volume={source_gain}[s{i}]")
                filters.append(f"[s{i}][m{i}]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=.95:latency=1[a{i}]")
            else:
                filters.append(f"[m{i}]anull[a{i}]")
            inputs.append(f"[a{i}]")
        elif audio:
            filters.append(f"[0:a:0]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,volume={source_gain}[a{i}]")
            inputs.append(f"[a{i}]")
    filters.append("".join(inputs) + f"concat=n={len(clips)}:v=1:a={int(has_audio)}[v]" + ("[a]" if has_audio else ""))
    args = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-threads", "2", "-i", str(source),
            ]
    if subtitle_path is not None:
        args += ["-f", "srt", "-i", str(subtitle_path)]
    if music_path is not None:
        args += ["-i", str(music_path)]
    args += ["-filter_complex_threads", "2", "-filter_complex", ";".join(filters), "-map", "[v]"]
    if has_audio:
        args += ["-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    if subtitle_path is not None:
        args += ["-map", "1:0", "-c:s", "mov_text", "-disposition:s:0", "default"]
    args += ["-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)]
    run(args, 300)
    return Path(output)

def build_visuals(source, folder, clips, metadata):
    """Extract genuine mid-scene stills and per-scene audio peak envelopes."""
    import array
    import sys
    folder = Path(folder)
    folder.mkdir(exist_ok=True)
    samples = array.array("h")
    rate = 8000
    if metadata["audio"]:
        pcm = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-threads", "2",
                              "-i", str(source), "-map", "0:a:0", "-vn", "-ac", "1",
                              "-ar", str(rate), "-t", str(MAX_DURATION), "-f", "s16le", "-"],
                             check=True, capture_output=True, timeout=90).stdout
        samples.frombytes(pcm)
        if sys.byteorder != "little":
            samples.byteswap()
    output = []
    for c in clips:
        i = c["id"]
        thumb = folder / f"{i}.jpg"
        at = (c["start"] + c["end"]) / 2
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(at), "-threads", "2",
             "-i", str(source), "-map", "0:v:0", "-frames:v", "1", "-vf",
             "scale=160:-2", "-threads", "1", "-q:v", "4", str(thumb)], 12)
        if not thumb.is_file():
            raise ValueError("Cannot extract scene thumbnail")
        peaks = []
        if metadata["audio"]:
            start, end = round(c["start"] * rate), round(c["end"] * rate)
            bins = min(96, max(8, math.ceil((c["end"] - c["start"]) * 12)))
            for j in range(bins):
                a = start + (end - start) * j // bins
                b = start + (end - start) * (j + 1) // bins
                window = samples[a:min(b, len(samples))]
                peaks.append(round(max((abs(v) for v in window), default=0) / 32768, 3))
        output.append({"id": i, "peaks": peaks})
    return output
