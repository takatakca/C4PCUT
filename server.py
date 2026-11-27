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

ROOT = Path(__file__).resolve().parent / "web"
LOCK = threading.Lock()
JOBS = {}
TOKEN = secrets.token_urlsafe(32)
HOST = "127.0.0.1:8765"

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
        if path == "/api/session":
            return self.reply({"token": TOKEN})
        static = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
        if path in static:
            name, mime = static[path]
            return self.file(ROOT / name, mime)
        parts = path.split("/")
        if len(parts) == 4 and parts[1:3] == ["api", "export"] and parts[3] in JOBS:
            return self.file(JOBS[parts[3]]["folder"] / "export.mp4", "video/mp4", True)
        if len(parts) == 5 and parts[1:3] == ["api", "thumbnail"] and parts[3] in JOBS:
            name = parts[4]
            if name.endswith(".jpg") and name[:-4].isascii() and name[:-4].isdigit() and len(name) <= 6:
                return self.file(JOBS[parts[3]]["folder"] / "visuals" / name, "image/jpeg")
        return self.reply({"error": "Not found"}, 404)

    def do_POST(self):
        if not self.valid_host() or self.headers.get("X-C4PCUT-Token") != TOKEN:
            return self.reply({"error": "Forbidden"}, 403)
        if not LOCK.acquire(blocking=False):
            return self.reply({"error": "Another media operation is running"}, 409)
        try:
            path = urlsplit(self.path).path
            size = int(self.headers.get("Content-Length", "0"))
            self.connection.settimeout(60)
            if path == "/api/import":
                if not 0 < size <= engine.MAX_BYTES or len(JOBS) >= 8:
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
            if not 0 < size <= 32768:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(size))
            job_id = payload["id"]
            job = JOBS[job_id]
            source = job["folder"] / "source.media"
            if path == "/api/analyze":
                job["clips"] = engine.analyze(source, job["metadata"])
                return self.reply({"clips": job["clips"]})
            if path == "/api/visuals":
                visuals = engine.build_visuals(source, job["folder"] / "visuals", job["clips"], job["metadata"])
                for item in visuals:
                    item["thumbnail"] = f"/api/thumbnail/{job_id}/{item['id']}.jpg"
                return self.reply({"visuals": visuals})
            if path == "/api/render":
                selected = engine.validate_edits(payload["clips"], job["clips"], payload.get("edits", {}))
                temp = job["folder"] / "rendering.mp4"
                try:
                    engine.render(source, temp, selected, job["metadata"]["audio"])
                    temp.replace(job["folder"] / "export.mp4")
                finally:
                    temp.unlink(missing_ok=True)
                return self.reply({"url": "/api/export/" + job_id})
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
    with tempfile.TemporaryDirectory(prefix="c4pcut-") as storage:
        with ThreadingHTTPServer(("127.0.0.1", 8765), Handler) as server:
            server.storage = storage
            print("C4PCUT: http://" + HOST, flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
