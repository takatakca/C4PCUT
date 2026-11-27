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

def render(source, output, clips, audio):
    # Normalize timestamps and concatenate independently trimmed video/audio streams.
    filters, inputs = [], []
    for i, c in enumerate(clips):
        a, b = c["start"], c["end"]
        filters.append(f"[0:v:0]trim=start={a}:end={b},setpts=PTS-STARTPTS,scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1[v{i}]")
        inputs.append(f"[v{i}]")
        if audio:
            filters.append(f"[0:a:0]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}]")
            inputs.append(f"[a{i}]")
    filters.append("".join(inputs) + f"concat=n={len(clips)}:v=1:a={int(audio)}[v]" + ("[a]" if audio else ""))
    args = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-threads", "2", "-i", str(source),
            "-filter_complex_threads", "2", "-filter_complex", ";".join(filters), "-map", "[v]"]
    if audio:
        args += ["-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    args += ["-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)]
    run(args, 300)
    return Path(output)
