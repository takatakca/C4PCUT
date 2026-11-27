"""Trusted, bounded FFmpeg operations for local development."""
import json
import math
import re
import subprocess
import tempfile
import time
from render_queue import Cancelled
from pathlib import Path

MAX_DURATION = 600
MAX_CLIPS = 60
MAX_BYTES = 250 * 1024 * 1024

def run(args, timeout=180, cwd=None):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout, cwd=cwd)

def run_render(args, duration, cancel, progress, cwd=None, timeout=300):
    """Poll FFmpeg machine-readable timestamps, with cancellation and a hard deadline."""
    if cancel is None:
        return run(args, timeout, cwd=cwd)
    if cancel.is_set():
        raise Cancelled()
    args=args[:1]+["-progress","pipe:1","-nostats"]+args[1:]
    with tempfile.TemporaryDirectory(prefix="c4pcut-progress-") as folder, tempfile.TemporaryFile() as errors:
        path=Path(folder)/"progress.log"
        with path.open("wb") as events, path.open("rb") as reader, subprocess.Popen(args,stdout=events,stderr=errors,cwd=cwd) as process:
            started=time.monotonic()
            fragment=b""
            try:
                while process.poll() is None:
                    if cancel.wait(.2):
                        raise Cancelled()
                    if time.monotonic()-started>timeout:
                        raise subprocess.TimeoutExpired(args,timeout)
                    # Separate file handles preserve independent read/write offsets.
                    data=reader.read(65536)
                    lines=(fragment+data).split(b"\n")
                    fragment=lines.pop()
                    for line in lines:
                        if line.startswith(b"out_time_us="):
                            try:
                                progress(int(line.split(b"=",1)[1])/1e6/max(.001,duration)*100)
                            except ValueError:
                                pass
                if cancel.is_set():
                    raise Cancelled()
                if process.returncode:
                    errors.seek(0)
                    raise subprocess.CalledProcessError(process.returncode,args,stderr=errors.read(8192))
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

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

EFFECTS = {"none": "", "mono": ",hue=s=0", "warm": ",colorbalance=rs=.06:bs=-.05", "contrast": ",eq=contrast=1.15:saturation=1.10", "fade": "", "zoom": ""}

def effect_filter(effect, duration, dimensions=None):
    if effect not in EFFECTS:
        raise ValueError("Unknown effect")
    if effect == "fade":
        # Non-overlapping fade through black, preserving the edit duration.
        fade = min(.35, duration/3)
        return f",fade=t=in:st=0:d={fade:.6f},fade=t=out:st={duration-fade:.6f}:d={fade:.6f}"
    if effect == "zoom":
        if dimensions is None:
            raise ValueError("Zoom requires normalized dimensions")
        w,h=dimensions
        frames=max(1,round(duration*30)-1)
        return f",zoompan=z='1+0.12*min(1,on/{frames})':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps=30,setsar=1"
    return EFFECTS[effect]

def validate_order(ids, order):
    """Explicit order must be a permutation of selected scene IDs."""
    if order is None:
        return sorted(ids)
    if not isinstance(order,list) or len(order)!=len(ids) or any(type(i) is not int for i in order) or len(set(order))!=len(order) or set(order)!=set(ids):
        raise ValueError("Scene order must contain each selected scene exactly once")
    return list(order)

def validate_edits(ids, clips, edits, order=None):
    validate_selection(ids, clips)
    selected = [clips[i] for i in validate_order(ids,order)]
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

EXPORT_FORMATS = {"original": None, "vertical": (720,1280), "square": (720,720), "landscape": (1280,720),
                  "vertical_hd": (1080,1920), "square_hd": (1080,1080), "landscape_hd": (1920,1080),
                  "landscape_qhd": (2560,1440), "vertical_qhd": (1440,2560),
                  "landscape_4k": (3840,2160), "vertical_4k": (2160,3840)}

def validate_format(preset, framing):
    if not isinstance(preset,str) or preset not in EXPORT_FORMATS:
        raise ValueError("Unknown export format")
    if not isinstance(framing,str) or framing not in {"fit","crop"}:
        raise ValueError("Unknown framing")
    return EXPORT_FORMATS[preset]

QUALITIES = {"compact": 28, "standard": 22, "high": 18}

def validate_quality(quality):
    if not isinstance(quality,str) or quality not in QUALITIES:
        raise ValueError("Unknown render quality")
    return QUALITIES[quality]

def validate_render_budget(preset, framing, duration, quality):
    dims=validate_format(preset,framing)
    validate_quality(quality)
    if dims and max(dims)>=3840 and duration>60:
        raise ValueError("4K export limited to 60 seconds")
    if dims and max(dims)>=2560 and duration>120:
        raise ValueError("QHD export limited to 120 seconds")

def render(source, output, clips, audio, subtitle_path=None, music_path=None, music_gain=.35, source_gain=1, burn_ass=None, preset="original", framing="fit", quality="standard", cancel=None, progress=None, title_ass=None):
    total=sum(c["end"]-c["start"] for c in clips)
    validate_render_budget(preset,framing,total,quality)
    progress=progress or (lambda value: None)
    # Normalize timestamps and concatenate independently trimmed video/audio streams.
    filters, inputs = [], []
    if burn_ass is not None and subtitle_path is not None:
        raise ValueError("Choose either embedded or burned-in captions")
    music_index = 2 if subtitle_path is not None else 1
    has_audio = audio or music_path is not None
    # A zoom operation needs a fixed output geometry and frame rate. Normalize
    # every scene in that sequence to keep concat inputs compatible.
    dimensions = validate_format(preset,framing)
    if dimensions is None and any(c.get("effect") == "zoom" for c in clips):
        info = probe(source)
        dimensions = (max(2,info["width"]//2*2),max(2,info["height"]//2*2))
    for i, c in enumerate(clips):
        a, b = c["start"], c["end"]
        if preset != "original":
            w,h = dimensions
            if framing == "fit":
                geometry = f"scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps=30"
            else:
                geometry = f"scale={w}:{h}:force_original_aspect_ratio=increase:force_divisible_by=2,crop={w}:{h},fps=30"
        else:
            geometry = f"scale={dimensions[0]}:{dimensions[1]},fps=30" if dimensions else "scale=trunc(iw/2)*2:trunc(ih/2)*2"
        effect = effect_filter(c.get("effect","none"), b-a, dimensions)
        filters.append(f"[0:v:0]trim=start={a}:end={b},setpts=PTS-STARTPTS,{geometry},setsar=1{effect}[v{i}]")
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
    video_label = "[joined]" if burn_ass is not None or title_ass is not None else "[v]"
    filters.append("".join(inputs) + f"concat=n={len(clips)}:v=1:a={int(has_audio)}" + video_label + ("[a]" if has_audio else ""))
    if burn_ass is not None or title_ass is not None:
        stages=[]
        if title_ass is not None:stages.append("ass=filename=titles.ass")
        if burn_ass is not None:stages.append("ass=filename=captions.ass")
        filters.append("[joined]"+",".join(stages)+"[v]")
    args = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-threads", "2", "-i", str(Path(source).resolve()),
            ]
    if subtitle_path is not None:
        args += ["-f", "srt", "-i", str(subtitle_path)]
    if music_path is not None:
        args += ["-i", str(Path(music_path).resolve())]
    args += ["-filter_complex_threads", "2", "-filter_complex", ";".join(filters), "-map", "[v]"]
    if has_audio:
        args += ["-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    if subtitle_path is not None:
        args += ["-map", "1:0", "-c:s", "mov_text", "-disposition:s:0", "default"]
    args += ["-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-crf", str(validate_quality(quality)), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(Path(output).resolve())]
    if burn_ass is not None or title_ass is not None:
        # Constant filter filenames, private working directory, no path interpolation.
        with tempfile.TemporaryDirectory(prefix="c4pcut-ass-") as working:
            if burn_ass is not None:(Path(working)/"captions.ass").write_text(burn_ass, encoding="utf-8")
            if title_ass is not None:(Path(working)/"titles.ass").write_text(title_ass, encoding="utf-8")
            run_render(args,total,cancel,progress,cwd=working,timeout=600 if preset.endswith(("4k","qhd")) else 300)
    else:
        run_render(args,total,cancel,progress,timeout=600 if preset.endswith(("4k","qhd")) else 300)
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
