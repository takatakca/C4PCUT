import http.client
import json
import shutil
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
import engine
import server
from usage import Ledger
from render_queue import RenderQueue, Cancelled

class RenderAPITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_export_and_cancel(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            ident="b"*32
            folder=root/ident
            folder.mkdir()
            source=folder/"source.media"
            engine.run(["ffmpeg","-nostdin","-y","-f","lavfi","-i","color=blue:s=160x120:r=25:d=1","-c:v","libx264","-pix_fmt","yuv420p","-f","mp4",str(source)])
            server.JOBS[ident]={"folder":folder,"metadata":engine.probe(source),"clips":[{"id":0,"start":0,"end":1}]}
            httpd=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
            httpd.storage=d
            httpd.persistent=False
            httpd.ledger=Ledger(root,2)
            thread=threading.Thread(target=httpd.serve_forever,daemon=True)
            thread.start()
            q=RenderQueue()
            def request(path,payload=None,auth=True):
                conn=http.client.HTTPConnection("127.0.0.1",httpd.server_port,timeout=5)
                try:
                    headers={"Host":server.HOST}
                    if auth:
                        headers["X-C4PCUT-Token"]=server.TOKEN
                    if payload is None:
                        conn.request("GET",path,headers=headers)
                    else:
                        headers["Content-Type"]="application/json"
                        conn.request("POST",path,json.dumps(payload),headers)
                    response=conn.getresponse()
                    return response.status,response.read()
                finally:
                    conn.close()
            def terminal(task):
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    code,data=request("/api/render/status",{"render_id":task})
                    self.assertEqual(code,200)
                    state=json.loads(data)
                    if state["status"] in ("completed","failed","cancelled"):
                        return state
                    time.sleep(.05)
                self.fail("Render did not terminate")
            try:
                with patch.object(server,"RENDERS",q):
                    payload={"id":ident,"clips":[0],"quality":"compact"}
                    code,data=request("/api/render",payload)
                    self.assertEqual(code,202)
                    task=json.loads(data)["render_id"]
                    self.assertEqual(request("/api/render/status",{"render_id":task},False)[0],403)
                    state=terminal(task)
                    self.assertEqual(state["status"],"completed")
                    self.assertEqual(state["progress"],100)
                    self.assertEqual(request(state["result"]["url"])[0],200)
                    previous=(folder/"export.mp4").read_bytes()
                    started=threading.Event()
                    def fake_render(*args,**kwargs):
                        Path(args[1]).write_bytes(b"partial")
                        started.set()
                        if kwargs["cancel"].wait(5):
                            raise Cancelled()
                        raise RuntimeError("Cancellation missing")
                    with patch.object(engine,"render",side_effect=fake_render):
                        code,data=request("/api/render",payload)
                        self.assertEqual(code,202)
                        task=json.loads(data)["render_id"]
                        self.assertTrue(started.wait(2))
                        self.assertEqual(request("/api/projects/delete",{"id":ident})[0],409)
                        self.assertEqual(request("/api/render/cancel",{"render_id":task})[0],200)
                        self.assertEqual(terminal(task)["status"],"cancelled")
                    self.assertEqual((folder/"export.mp4").read_bytes(),previous)
                    self.assertFalse((folder/"rendering.mp4").exists())
                    code,raw=request("/api/usage")
                    self.assertEqual(code,200)
                    summary=json.loads(raw)
                    self.assertEqual(summary["attempted_seconds"],2)
                    self.assertEqual(summary["remaining_seconds"],0)
                    self.assertEqual(summary["outcomes"]["completed"]["attempts"],1)
                    self.assertEqual(summary["outcomes"]["cancelled"]["attempts"],1)
                    self.assertEqual(request("/api/render",payload)[0],429)
                    self.assertEqual(httpd.ledger.summary(),summary)
            finally:
                q.shutdown()
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
                server.JOBS.pop(ident,None)
