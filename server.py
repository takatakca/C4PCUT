"""Single-user localhost prototype. Not a production HTTP service."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import secrets
import shutil
import tempfile
import threading
from urllib.parse import urlsplit
import engine
import captions
import music
import director
import clipper
import projects
from render_queue import RenderQueue, Cancelled
from contextlib import nullcontext
import re
import os
import sys

ROOT = Path(__file__).resolve().parent / "web"
LOCK = threading.Lock()
JOBS = {}
RENDERS = RenderQueue()
TOKEN = secrets.token_urlsafe(32)
HOST = "127.0.0.1:8765"
# Docker publishes only on host loopback. Never enable a public proxy for this prototype.
BIND = "0.0.0.0" if os.environ.get("C4PCUT_CONTAINER") == "1" else "127.0.0.1"

class Handler(BaseHTTPRequestHandler):
    def reply(self, obj, status=200):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def file(self, path, mime, download=False):
        if not path.is_file():
            return self.reply({"error": "Not found"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        if download:
            self.send_header("Content-Disposition", 'attachment; filename="c4pcut-export.mp4"')
        self.end_headers()
        with path.open("rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def valid_host(self):
        return self.headers.get("Host") in {HOST, "localhost:8765"}

    def do_GET(self):
        if not self.valid_host():
            return self.reply({"error": "Invalid host"}, 403)
        path = urlsplit(self.path).path
        if path == "/healthz":
            return self.reply({"status": "ok", "mode": "private-local"})
        if path == "/api/session":
            return self.reply({"token": TOKEN})
        static = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
        if path in static:
            name, mime = static[path]
            return self.file(ROOT / name, mime)
        parts = path.split("/")
        if len(parts) == 4 and parts[1:3] == ["api", "source"] and parts[3] in JOBS:
            return self.file(JOBS[parts[3]]["folder"] / "source.media", "application/octet-stream")
        if len(parts) == 4 and parts[1:3] == ["api", "export"] and parts[3] in JOBS:
            return self.file(JOBS[parts[3]]["folder"] / "export.mp4", "video/mp4", True)
        if len(parts) == 4 and parts[1:3] == ["api", "captions"] and parts[3] in JOBS:
            return self.file(JOBS[parts[3]]["folder"] / "export.srt", "application/x-subrip")
        if len(parts) == 6 and parts[1:3] == ["api", "clipper"] and parts[3] in JOBS:
            job = JOBS[parts[3]]
            batch, name = parts[4], parts[5]
            if batch == job.get("clip_batch") and re.fullmatch(r"[0-9]\.mp4", name):
                return self.file(job["folder"] / "clips" / name, "video/mp4", True)
        if len(parts) == 5 and parts[1:3] == ["api", "thumbnail"] and parts[3] in JOBS:
            name = parts[4]
            if name.endswith(".jpg") and name[:-4].isascii() and name[:-4].isdigit() and len(name) <= 6:
                return self.file(JOBS[parts[3]]["folder"] / "visuals" / name, "image/jpeg")
        return self.reply({"error": "Not found"}, 404)

    def do_POST(self):
        if not self.valid_host() or self.headers.get("X-C4PCUT-Token") != TOKEN:
            return self.reply({"error": "Forbidden"}, 403)
        path = urlsplit(self.path).path
        if path in {"/api/render/status","/api/render/cancel"}:
            try:
                self.connection.settimeout(10)
                size=int(self.headers.get("Content-Length","0"))
                if not 0<size<=1024:
                    raise ValueError("Invalid request")
                ident=json.loads(self.rfile.read(size))["render_id"]
                if not isinstance(ident,str) or not projects.ID.fullmatch(ident):
                    raise ValueError("Invalid render ID")
                if path.endswith("/cancel"):
                    RENDERS.cancel(ident)
                return self.reply(RENDERS.status(ident))
            except (ValueError,KeyError,TypeError):
                return self.reply({"error":"Unknown render"},400)
        if not LOCK.acquire(blocking=False):
            return self.reply({"error": "Another media operation is running"}, 409)
        try:
            if RENDERS.busy() and path != "/api/render":
                return self.reply({"error":"Render queue active; cancel or wait for completion"},409)
            size = int(self.headers.get("Content-Length", "0"))
            self.connection.settimeout(60)
            if path == "/api/import":
                if not 0 < size <= engine.MAX_BYTES or sum(1 for p in Path(self.server.storage).iterdir() if projects.ID.fullmatch(p.name) and p.is_dir()) >= projects.MAX_PROJECTS:
                    raise ValueError("Maximum 250 MB per video and 8 imports per session")
                job_id = secrets.token_hex(16)
                folder = Path(self.server.storage) / job_id
                folder.mkdir()
                source = folder / "source.media"
                try:
                    with source.open("wb") as f:
                        remaining = size
                        while remaining:
                            chunk = self.rfile.read(min(remaining, 1024 * 1024))
                            if not chunk:
                                raise ValueError("Incomplete upload")
                            f.write(chunk)
                            remaining -= len(chunk)
                    metadata = engine.probe(source)
                except Exception:
                    shutil.rmtree(folder, ignore_errors=True)
                    raise
                JOBS[job_id] = {"folder": folder, "metadata": metadata}
                return self.reply({"id": job_id, **metadata})
            if path.startswith("/api/music/import/"):
                job_id = path.split("/")[-1]
                job = JOBS[job_id]
                if not 0 < size <= music.MAX_MUSIC_BYTES:
                    raise ValueError("Maximum music upload is 64 MB")
                raw = job["folder"] / "music-upload.media"
                # A separate immutable version keeps previous state safe if
                # normalization fails; only one music track per active job.
                temp_music = job["folder"] / "music-pending.wav"
                try:
                    with raw.open("wb") as out:
                        remaining = size
                        while remaining:
                            chunk = self.rfile.read(min(remaining,1024*1024))
                            if not chunk:
                                raise ValueError("Incomplete music upload")
                            out.write(chunk)
                            remaining -= len(chunk)
                    duration = job["metadata"]["duration"]
                    music.normalize(raw, temp_music, duration)
                    data = music.analyze(temp_music, duration)
                    temp_music.replace(job["folder"] / "music.wav")
                    job["music_analysis"] = data
                    return self.reply(data)
                finally:
                    raw.unlink(missing_ok=True)
                    temp_music.unlink(missing_ok=True)
            if not 0 < size <= 262144:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(size))
            if path == "/api/projects/list":
                return self.reply({"projects":projects.list_saved(Path(self.server.storage)), "persistent":self.server.persistent})
            job_id = payload["id"]
            if not isinstance(job_id,str) or not projects.ID.fullmatch(job_id):
                raise ValueError("Invalid project ID")
            if path == "/api/projects/open":
                folder=Path(self.server.storage)/job_id
                if not folder.is_dir() or folder.is_symlink():
                    raise ValueError("Project not found")
                job,state=projects.restore(folder)
                JOBS[job_id]=job
                return self.reply({"id":job_id,**job["metadata"],"clips":job["clips"],"state":state,"music":job.get("music_analysis"),"source_url":"/api/source/"+job_id})
            if path == "/api/projects/delete":
                folder=Path(self.server.storage)/job_id
                if not folder.is_dir() or folder.is_symlink():
                    raise ValueError("Project not found")
                shutil.rmtree(folder)
                JOBS.pop(job_id,None)
                return self.reply({"deleted":True})
            job = JOBS[job_id]
            if path == "/api/projects/save":
                state=projects.save(job,payload)
                return self.reply({"saved":True,"name":state["name"]})
            source = job["folder"] / "source.media"
            if path == "/api/analyze":
                job["clips"] = engine.analyze(source, job["metadata"])
                return self.reply({"clips": job["clips"]})
            if path == "/api/visuals":
                visuals = engine.build_visuals(source, job["folder"] / "visuals", job["clips"], job["metadata"])
                for item in visuals:
                    item["thumbnail"] = f"/api/thumbnail/{job_id}/{item['id']}.jpg"
                return self.reply({"visuals": visuals})
            if path == "/api/captions/import":
                return self.reply({"cues": captions.parse_srt(payload["srt"], job["metadata"]["duration"])})
            if path == "/api/transcribe":
                model = os.environ.get("C4PCUT_WHISPER_MODEL")
                if not model or not Path(model).is_dir():
                    return self.reply({"error": "Configure C4PCUT_WHISPER_MODEL with a local Faster Whisper model directory"}, 503)
                if not job["metadata"]["audio"]:
                    return self.reply({"error": "No source audio to transcribe"}, 400)
                result = engine.run([sys.executable, str(Path(__file__).resolve().parent / "transcribe.py"), str(source), model], 600)
                cues = json.loads(result.stdout)
                duration = job["metadata"]["duration"]
                cues = [{**c, "end": min(c["end"], duration)} for c in cues if c["start"] < duration]
                return self.reply({"cues": captions.validate(cues, duration)})
            if path == "/api/music/analyze":
                use_music = payload.get("use_music", False)
                if type(use_music) is not bool:
                    raise ValueError("Invalid music selection")
                if use_music:
                    return self.reply(job["music_analysis"])
                if not job["metadata"]["audio"]:
                    return self.reply({"error": "No source audio to analyze"}, 400)
                data = music.analyze(source, job["metadata"]["duration"])
                job["source_music_analysis"] = data
                return self.reply(data)
            if path == "/api/music/cuts":
                use_music = payload.get("use_music", False)
                if type(use_music) is not bool:
                    raise ValueError("Invalid music selection")
                data = job["music_analysis" if use_music else "source_music_analysis"]
                if not data["beats"]:
                    return self.reply({"error": "No usable audio onsets found"}, 400)
                job["clips"] = music.beat_cuts(job["metadata"]["duration"], data["beats"], payload.get("interval", 2))
                return self.reply({"clips": job["clips"]})
            if path == "/api/director":
                cues = captions.validate(payload.get("cues", []), job["metadata"]["duration"])
                use_music = payload.get("use_music", False)
                if type(use_music) is not bool:
                    raise ValueError("Invalid music selection")
                analysis = job.get("music_analysis" if use_music else "source_music_analysis", {})
                result = director.plan(payload.get("prompt"), payload.get("target"), payload.get("style"),
                                       payload.get("provider"), job["clips"], cues, analysis.get("beats", []))
                return self.reply(result)
            if path == "/api/clipper/suggest":
                cues = captions.validate(payload.get("cues", []), job["metadata"]["duration"])
                use_music = payload.get("use_music", False)
                if type(use_music) is not bool:
                    raise ValueError("Invalid music selection")
                analysis = job.get("music_analysis" if use_music else "source_music_analysis", {})
                if not analysis and not use_music and job["metadata"]["audio"]:
                    analysis = music.analyze(source, job["metadata"]["duration"])
                    job["source_music_analysis"] = analysis
                suggestions = clipper.suggest(job["metadata"]["duration"], job["clips"], cues,
                                              analysis.get("beats", []), payload.get("target"), payload.get("count"), payload.get("style"))
                # Replace a previous batch only after valid suggestions.
                folder = job["folder"] / "clips"
                shutil.rmtree(folder, ignore_errors=True)
                folder.mkdir()
                job["clip_batch"] = secrets.token_hex(12)
                job["clip_candidates"] = suggestions
                job["clip_scenes"] = [dict(c) for c in job["clips"]]
                return self.reply({"batch":job["clip_batch"],"candidates":suggestions})
            if path == "/api/clipper/render":
                if payload.get("batch") != job.get("clip_batch") or not job.get("clip_batch"):
                    raise ValueError("Generate suggestions first")
                index = payload.get("index")
                if type(index) is not int or not 0 <= index < len(job["clip_candidates"]):
                    raise ValueError("Invalid clip index")
                candidate = job["clip_candidates"][index]
                selected = clipper.ranges(candidate, job["clip_scenes"])
                cues = captions.validate(payload.get("cues", []), job["metadata"]["duration"])
                mapped = captions.remap(cues, selected)
                caption_mode = captions.validate_mode(payload.get("caption_mode", "soft"))
                use_music = payload.get("use_music", False)
                if type(use_music) is not bool:
                    raise ValueError("Invalid music selection")
                music_path = job["folder"] / "music.wav" if use_music else None
                if music_path is not None and not music_path.is_file():
                    raise ValueError("Import music first")
                music_gain = music.validate_gain(payload.get("music_gain", .35))
                source_gain = music.validate_gain(payload.get("source_gain", 1))
                folder = job["folder"] / "clips"
                temp, subtitle = folder / "pending.mp4", folder / "pending.srt"
                try:
                    if mapped:
                        subtitle.write_text(captions.to_srt(mapped),encoding="utf-8")
                    burn = captions.to_ass(mapped,caption_mode) if mapped and caption_mode != "soft" else None
                    engine.render(source,temp,selected,job["metadata"]["audio"],subtitle if mapped and caption_mode=="soft" else None,music_path,music_gain,source_gain,burn_ass=burn, preset=payload.get('preset','original'), framing=payload.get('framing','fit'), quality=payload.get('quality','standard'))
                    temp.replace(folder / f"{index}.mp4")
                finally:
                    temp.unlink(missing_ok=True)
                    subtitle.unlink(missing_ok=True)
                return self.reply({"url":f"/api/clipper/{job_id}/{job['clip_batch']}/{index}.mp4"})
            if path == "/api/render":
                selected = engine.validate_edits(payload["clips"], job["clips"], payload.get("edits", {}))
                cues = captions.validate(payload.get("cues", []), job["metadata"]["duration"])
                mapped = captions.remap(cues, selected)
                caption_mode = captions.validate_mode(payload.get("caption_mode", "soft"))
                use_music = payload.get("use_music", False)
                if type(use_music) is not bool:
                    raise ValueError("Invalid music selection")
                music_path = job["folder"] / "music.wav" if use_music else None
                if music_path is not None and not music_path.is_file():
                    raise ValueError("Import music first")
                music_gain = music.validate_gain(payload.get("music_gain", .35))
                source_gain = music.validate_gain(payload.get("source_gain", 1))
                preset,framing,quality=payload.get("preset","original"),payload.get("framing","fit"),payload.get("quality","standard")
                engine.validate_render_budget(preset,framing,sum(c["end"]-c["start"] for c in selected),quality)
                folder=job["folder"]
                audio=job["metadata"]["audio"]
                def work(cancel,progress):
                    temp=folder/"rendering.mp4"
                    subtitle=folder/"rendering.srt"
                    exported_srt=folder/"export.srt"
                    try:
                        if mapped:
                            subtitle.write_text(captions.to_srt(mapped),encoding="utf-8")
                        burn=captions.to_ass(mapped,caption_mode) if mapped and caption_mode!="soft" else None
                        engine.render(source,temp,selected,audio,subtitle if mapped and caption_mode=="soft" else None,
                                      music_path,music_gain,source_gain,burn_ass=burn,preset=preset,framing=framing,
                                      quality=quality,cancel=cancel,progress=progress)
                        if cancel.is_set():
                            raise Cancelled()
                        temp.replace(folder/"export.mp4")
                        if mapped:
                            subtitle.replace(exported_srt)
                        else:
                            exported_srt.unlink(missing_ok=True)
                        return {"url":"/api/export/"+job_id,"captions_url":"/api/captions/"+job_id if mapped else None}
                    finally:
                        temp.unlink(missing_ok=True)
                        subtitle.unlink(missing_ok=True)
                ident=RENDERS.submit(job_id,work)
                return self.reply({"render_id":ident},202)
            return self.reply({"error": "Not found"}, 404)
        except (ValueError, KeyError, TypeError):
            return self.reply({"error": "Invalid input or unsupported media"}, 400)
        except Exception as exc:
            self.log_error("Media operation failed: %s", type(exc).__name__)
            return self.reply({"error": "Media operation failed; check server logs and FFmpeg installation"}, 500)
        finally:
            LOCK.release()

if __name__ == "__main__":
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("Install FFmpeg and ffprobe first")
    root=os.environ.get("C4PCUT_DATA_DIR")
    if root:
        root=Path(root).resolve()
        root.mkdir(mode=0o700,parents=True,exist_ok=True)
    context=nullcontext(root) if root else tempfile.TemporaryDirectory(prefix="c4pcut-")
    with context as storage:
        with ThreadingHTTPServer((BIND, 8765), Handler) as server:
            server.storage = storage
            server.persistent = bool(root)
            print("C4PCUT: http://" + HOST, flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                RENDERS.shutdown()
