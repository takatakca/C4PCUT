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
import owner_auth
import usage
import workspaces
import studio_pack
import studio_gateway
import capabilities
import hashlib
import time
from render_queue import RenderQueue, Cancelled
from contextlib import nullcontext
import re
import os
import sys

ROOT = Path(__file__).resolve().parent / "web"
LOCK = threading.Lock()
GATEWAY_UPLOADS = threading.BoundedSemaphore(1)
JOBS = {}
RENDERS = RenderQueue()
TOKEN = secrets.token_urlsafe(32)
HOST = "127.0.0.1:8765"
# Docker publishes only on host loopback. Never enable a public proxy for this prototype.
BIND = "0.0.0.0" if os.environ.get("C4PCUT_CONTAINER") == "1" else "127.0.0.1"

class Handler(BaseHTTPRequestHandler):
    def security_headers(self):
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Cross-Origin-Resource-Policy","same-origin")
        self.send_header("Content-Security-Policy","default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.send_header("Permissions-Policy","camera=(), microphone=(), geolocation=()")

    def owner_allowed(self):
        registry=getattr(self.server,"workspaces",None)
        if registry is not None:
            gateway=getattr(self.server,"studio_gateway",None)
            if gateway is not None:
                principal=gateway.verify(self.headers.get("X-C4PCUT-Gateway"),self.command,self.path)
                workspace=registry.get(principal.workspace) if principal is not None else None
                self.gateway_principal=principal
            else:
                workspace=workspaces.authenticate(self.headers.get("Authorization"),registry)
            if workspace is not None:
                self.scope=workspace.slug
                self.jobs=workspace.jobs
                self.storage=workspace.storage
                self.ledger=workspace.ledger
                self.csrf_token=workspace.token
                self.policy=workspace.policy
                self.plan=None
                self.request_limit=None
                if gateway is not None:
                    profiles=getattr(self.server,"plan_profiles",{})
                    profile=profiles.get(principal.plan)
                    if profile is None:
                        return self.reply_denied()
                    self.plan=principal.plan
                    self.policy=capabilities.intersect(profile.policy,workspace.policy)
                    self.request_limit=profile.monthly_render_seconds
                return True
        elif owner_auth.authorized(self.headers.get("Authorization"),getattr(self.server,"owner_digest",None)):
            self.scope=None
            self.jobs=JOBS
            self.storage=getattr(self.server,"storage",None)
            self.ledger=getattr(self.server,"ledger",None)
            self.csrf_token=TOKEN
            self.policy=None
            self.plan=None
            self.request_limit=None
            return True
        return self.reply_denied()

    def reply_denied(self):
        data=b'{"error":"Private editor authentication required"}'
        self.send_response(401)
        if getattr(self.server,"studio_gateway",None) is None:
            self.send_header("WWW-Authenticate",'Basic realm="C4PCUT private editor", charset="UTF-8"')
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)))
        self.send_header("Cache-Control","no-store")
        self.security_headers()
        self.end_headers()
        self.wfile.write(data)
        return False

    def reply(self, obj, status=200):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.security_headers()
        self.end_headers()
        self.wfile.write(data)

    def file(self, path, mime, download=False):
        if not path.is_file():
            return self.reply({"error": "Not found"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.security_headers()
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
        if not self.owner_allowed():
            return
        if getattr(self,"gateway_principal",None) is not None and (self.headers.get("Transfer-Encoding") is not None or self.headers.get_all("Content-Length",[]) not in ([],["0"])):
            return self.reply({"error":"Unexpected GET body"},400)
        if path == "/api/usage":
            return self.reply(self.ledger.summary(self.request_limit) if self.ledger else {"enabled":False})
        if path == "/api/session":
            return self.reply({"token": self.csrf_token, "workspace": self.scope, "plan":self.plan, "capabilities":self.policy.public() if self.policy else None})
        static = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript"), "/plan-ui.js": ("plan-ui.js", "text/javascript"), "/effect-preview.js": ("effect-preview.js", "text/javascript"), "/sequence-preview.js": ("sequence-preview.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
        if path in static:
            name, mime = static[path]
            return self.file(ROOT / name, mime)
        parts = path.split("/")
        if len(parts) == 4 and parts[1:3] == ["api", "source"] and parts[3] in self.jobs:
            return self.file(self.jobs[parts[3]]["folder"] / "source.media", "application/octet-stream")
        if len(parts) == 4 and parts[1:3] == ["api", "soundtrack"] and parts[3] in self.jobs:
            if self.policy and "music" not in self.policy.features:
                return self.reply({"error":"Feature unavailable in this workspace"},403)
            path=self.jobs[parts[3]]["folder"] / "music.wav"
            if path.is_symlink() or not path.is_file():
                return self.reply({"error":"Not found"},404)
            return self.file(path,"audio/wav")
        if len(parts) == 4 and parts[1:3] == ["api", "export"] and parts[3] in self.jobs:
            return self.file(self.jobs[parts[3]]["folder"] / "export.mp4", "video/mp4", True)
        if len(parts) == 4 and parts[1:3] == ["api", "captions"] and parts[3] in self.jobs:
            return self.file(self.jobs[parts[3]]["folder"] / "export.srt", "application/x-subrip")
        if len(parts) == 6 and parts[1:3] == ["api", "clipper"] and parts[3] in self.jobs:
            job = self.jobs[parts[3]]
            batch, name = parts[4], parts[5]
            if batch == job.get("clip_batch") and re.fullmatch(r"[0-9]\.mp4", name):
                return self.file(job["folder"] / "clips" / name, "video/mp4", True)
        if len(parts) == 5 and parts[1:3] == ["api", "thumbnail"] and parts[3] in self.jobs:
            name = parts[4]
            if name.endswith(".jpg") and name[:-4].isascii() and name[:-4].isdigit() and len(name) <= 6:
                return self.file(self.jobs[parts[3]]["folder"] / "visuals" / name, "image/jpeg")
        return self.reply({"error": "Not found"}, 404)

    def do_POST(self):
        if not self.valid_host():
            return self.reply({"error":"Invalid host"},403)
        if not self.owner_allowed():
            return
        if not owner_auth.allowed_origin(self.headers.get("Origin"),self.headers.get("Host"),self.headers.get("Sec-Fetch-Site")) or not secrets.compare_digest(self.headers.get("X-C4PCUT-Token","").encode("utf-8"),self.csrf_token.encode("utf-8")):
            return self.reply({"error": "Forbidden"}, 403)
        path = urlsplit(self.path).path
        if getattr(self,"gateway_principal",None) is not None:
            # Authenticate before receiving a body. Stage bytes, verify digest,
            # then replay only the verified bytes through existing handlers.
            limit=engine.MAX_BYTES if path=="/api/import" else music.MAX_MUSIC_BYTES if path.startswith("/api/music/import/") else 262144
            if path in {"/api/render/status","/api/render/cancel"}:
                limit=1024
            if self.headers.get("Transfer-Encoding") is not None:
                return self.reply({"error":"Chunked requests unsupported"},400)
            lengths=self.headers.get_all("Content-Length",[])
            if len(lengths)!=1 or not re.fullmatch(r"[0-9]{1,10}",lengths[0]):
                return self.reply({"error":"Invalid content length"},400)
            size=int(lengths[0])
            if not 0<size<=limit:
                return self.reply({"error":"Invalid request size"},400)
            # Limit concurrent gateway body staging independent of render queue.
            if not GATEWAY_UPLOADS.acquire(blocking=False):
                return self.reply({"error":"Gateway upload busy"},409)
            try:
                self.connection.settimeout(10)
                deadline=time.monotonic()+60
                with tempfile.TemporaryFile() as verified:
                    digest=hashlib.sha256()
                    remaining=size
                    while remaining:
                        if time.monotonic()>deadline:
                            return self.reply({"error":"Upload deadline exceeded"},408)
                        chunk=self.rfile.read1(min(remaining,1024*1024))
                        if not chunk:
                            return self.reply({"error":"Incomplete body"},400)
                        remaining-=len(chunk)
                        digest.update(chunk)
                        verified.write(chunk)
                    if not secrets.compare_digest(digest.hexdigest(),self.gateway_principal.body_sha256):
                        return self.reply({"error":"Request body signature mismatch"},403)
                    verified.seek(0)
                    original=self.rfile
                    self.rfile=verified
                    try:
                        return self.dispatch_post(path)
                    finally:
                        self.rfile=original
            except (OSError,TimeoutError):
                return self.reply({"error":"Gateway body read failed"},400)
            finally:
                GATEWAY_UPLOADS.release()
        return self.dispatch_post(path)

    def dispatch_post(self,path):
        # Scope restrictions to new operations, not project recovery/deletion or old downloads.
        feature={"/api/transcribe":"transcribe","/api/clipper/suggest":"clipper","/api/clipper/render":"clipper","/api/music/analyze":"music","/api/music/cuts":"music","/api/studio/import-pack":"studio_pack"}.get(path)
        if path.startswith("/api/music/import/"):
            feature="music"
        if self.policy and feature and feature not in self.policy.features:
            return self.reply({"error":"Feature unavailable in this workspace"},403)
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
                    RENDERS.cancel(ident,self.scope)
                return self.reply(RENDERS.status(ident,self.scope))
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
                if not 0 < size <= engine.MAX_BYTES or sum(1 for p in Path(self.storage).iterdir() if projects.ID.fullmatch(p.name) and p.is_dir()) >= (self.policy.max_projects if self.policy else projects.MAX_PROJECTS):
                    raise ValueError("Maximum 250 MB per video and 8 imports per session")
                job_id = secrets.token_hex(16)
                folder = Path(self.storage) / job_id
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
                self.jobs[job_id] = {"folder": folder, "metadata": metadata}
                return self.reply({"id": job_id, **metadata})
            if path.startswith("/api/music/import/"):
                job_id = path.split("/")[-1]
                job = self.jobs[job_id]
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
            if path == "/api/studio/import-pack":
                if size>studio_pack.MAX_PACK_BYTES:
                    raise ValueError("Studio pack too large")
                brief=studio_pack.parse_pack(payload)
                return self.reply({"brief":brief,"director_prompt":studio_pack.director_prompt(brief)})
            if path == "/api/projects/list":
                return self.reply({"projects":projects.list_saved(Path(self.storage)), "persistent":self.server.persistent})
            job_id = payload["id"]
            if not isinstance(job_id,str) or not projects.ID.fullmatch(job_id):
                raise ValueError("Invalid project ID")
            if path == "/api/projects/open":
                folder=Path(self.storage)/job_id
                if not folder.is_dir() or folder.is_symlink():
                    raise ValueError("Project not found")
                job,state=projects.restore(folder)
                self.jobs[job_id]=job
                return self.reply({"id":job_id,**job["metadata"],"clips":job["clips"],"state":state,"director_prompt":studio_pack.director_prompt(state["studio_brief"]) if state["studio_brief"] else "","music":job.get("music_analysis"),"source_url":"/api/source/"+job_id})
            if path == "/api/projects/delete":
                folder=Path(self.storage)/job_id
                if not folder.is_dir() or folder.is_symlink():
                    raise ValueError("Project not found")
                shutil.rmtree(folder)
                self.jobs.pop(job_id,None)
                return self.reply({"deleted":True})
            job = self.jobs[job_id]
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
                if self.policy and payload.get("provider")=="ollama":
                    self.policy.require("ollama")
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
                preset,framing,quality=payload.get("preset","original"),payload.get("framing","fit"),payload.get("quality","standard")
                duration=sum(c["end"]-c["start"] for c in selected)
                engine.validate_render_budget(preset,framing,duration,quality)
                if self.policy:
                    self.policy.render(preset,framing,quality,duration,job["metadata"],caption_mode,use_music)
                ledger=self.ledger
                usage_id=ledger.reserve(job_id,"clipper",duration,self.request_limit) if ledger else None
                outcome="failed"
                folder = job["folder"] / "clips"
                temp, subtitle = folder / "pending.mp4", folder / "pending.srt"
                try:
                    if mapped:
                        subtitle.write_text(captions.to_srt(mapped),encoding="utf-8")
                    burn = captions.to_ass(mapped,caption_mode) if mapped and caption_mode != "soft" else None
                    engine.render(source,temp,selected,job["metadata"]["audio"],subtitle if mapped and caption_mode=="soft" else None,music_path,music_gain,source_gain,burn_ass=burn, preset=payload.get('preset','original'), framing=payload.get('framing','fit'), quality=payload.get('quality','standard'))
                    temp.replace(folder / f"{index}.mp4")
                    outcome="completed"
                finally:
                    try:
                        temp.unlink(missing_ok=True)
                        subtitle.unlink(missing_ok=True)
                    finally:
                        if ledger:
                            ledger.finish(usage_id,outcome)
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
                duration=sum(c["end"]-c["start"] for c in selected)
                engine.validate_render_budget(preset,framing,duration,quality)
                if self.policy:
                    self.policy.render(preset,framing,quality,duration,job["metadata"],caption_mode,use_music)
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
                ledger=self.ledger
                usage_id=ledger.reserve(job_id,"main",duration,self.request_limit) if ledger else None
                try:
                    ident=RENDERS.submit(job_id,work,on_finish=(lambda status:ledger.finish(usage_id,status)) if ledger else None,scope=self.scope)
                except Exception:
                    if ledger:
                        ledger.finish(usage_id,"rejected")
                    raise
                return self.reply({"render_id":ident},202)
            return self.reply({"error": "Not found"}, 404)
        except capabilities.CapabilityDenied:
            return self.reply({"error":"Operation exceeds workspace capabilities"},403)
        except usage.QuotaExceeded:
            return self.reply({"error":"Monthly render-attempt quota exceeded"},429)
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
    password=os.environ.pop("C4PCUT_OWNER_PASSWORD",None)
    try:
        digest=owner_auth.password_digest(password) if password is not None else None
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    del password
    config=os.environ.get("C4PCUT_WORKSPACES_FILE")
    gateway_config=os.environ.get("C4PCUT_GATEWAY_MAPPING_FILE")
    gateway_key=os.environ.get("C4PCUT_GATEWAY_KEY_FILE")
    profile_file=os.environ.get("C4PCUT_PLAN_PROFILES_FILE")
    if (gateway_config or gateway_key or profile_file) and not (gateway_config and gateway_key and config and profile_file):
        raise SystemExit("Gateway mode requires explicit plan profiles, mapping, key and workspaces")
    if (gateway_config or gateway_key) and not (gateway_config and gateway_key and config):
        raise SystemExit("Gateway mode requires mapping, key file and workspace mode")
    if config and digest is not None:
        raise SystemExit("Workspace mode and owner password mode are mutually exclusive")
    root=os.environ.get("C4PCUT_DATA_DIR")
    if config and not root:
        raise SystemExit("Workspace mode requires an explicit persistent data directory")
    if root:
        root=Path(root).resolve()
        root.mkdir(mode=0o700,parents=True,exist_ok=True)
    context=nullcontext(root) if root else tempfile.TemporaryDirectory(prefix="c4pcut-")
    with context as storage:
        with ThreadingHTTPServer((BIND, 8765), Handler) as server:
            server.storage = storage
            server.owner_digest = digest
            server.persistent = bool(root)
            try:
                limit=usage.limit_from_env(os.environ.get("C4PCUT_MONTHLY_RENDER_SECONDS"))
                if config and limit is not None:
                    raise ValueError("Set quotas in workspace configuration, not global environment")
                server.workspaces=workspaces.load(config,storage) if config else None
                server.plan_profiles=None
                if profile_file:
                    path=Path(profile_file)
                    if not path.is_file() or path.stat().st_size>32768:
                        raise ValueError("Invalid plan profile file")
                    server.plan_profiles=capabilities.parse_profiles(json.loads(path.read_text(encoding="utf-8")))
                server.studio_gateway=studio_gateway.load(gateway_config,gateway_key,server.workspaces,storage) if gateway_config else None
                server.ledger=None if config else usage.Ledger(storage,limit)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            print("C4PCUT: http://" + HOST, flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                RENDERS.shutdown()
