import json
import tempfile
import unittest
import threading
import http.client
import base64
from pathlib import Path
from http.server import ThreadingHTTPServer
import capabilities
import workspaces
import owner_auth
import server
import engine

def config():
    return {"max_output_edge":1280,"max_render_seconds":30,"max_projects":1,
            "qualities":["compact"],"features":["clipper"]}

class CapabilityTests(unittest.TestCase):
    def test_explicit_limits(self):
        policy=capabilities.parse(config())
        meta={"width":3840,"height":2160}
        policy.render("landscape","fit","compact",30,meta,"soft",False)
        for preset,quality,duration,mode,music in [("original","compact",5,"soft",False),("vertical_hd","compact",5,"soft",False),("landscape","high",5,"soft",False),("landscape","compact",31,"soft",False),("landscape","compact",5,"bold",False),("landscape","compact",5,"soft",True)]:
            with self.assertRaises(capabilities.CapabilityDenied):
                policy.render(preset,"fit",quality,duration,meta,mode,music)
        for patch in [{"max_projects":9},{"max_render_seconds":0},{"max_output_edge":True},{"qualities":[]},{"features":["unknown"]},{"features":["clipper","clipper"]}]:
            with self.assertRaises(ValueError):
                capabilities.parse({**config(),**patch})
    def test_http_rejects_before_render_accounting(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            password="test workspace password long"
            cfg=root/"config.json"
            cfg.write_text(json.dumps({"alpha":{"password_sha256":owner_auth.password_digest(password).hex(),"monthly_render_seconds":60,"capabilities":config()}}))
            registry=workspaces.load(cfg,root)
            ws=registry["alpha"]
            ident="a"*32
            folder=ws.storage/ident;folder.mkdir()
            (folder/"source.media").write_bytes(b"not used")
            ws.jobs[ident]={"folder":folder,"metadata":{"duration":4,"width":3840,"height":2160,"audio":False},"clips":engine.segments(4,[])}
            httpd=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
            httpd.workspaces=registry;httpd.persistent=True
            thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
            def req(path,payload=None):
                conn=http.client.HTTPConnection("127.0.0.1",httpd.server_port,timeout=5)
                headers={"Host":server.HOST,"Authorization":"Basic "+base64.b64encode(("alpha:"+password).encode()).decode(),"X-C4PCUT-Token":ws.token}
                try:
                    conn.request("GET" if payload is None else "POST",path,json.dumps(payload) if payload is not None else None,headers)
                    r=conn.getresponse();return r.status,json.loads(r.read())
                finally:conn.close()
            try:
                self.assertEqual(req("/api/session")[1]["capabilities"]["max_output_edge"],1280)
                self.assertEqual(req("/api/transcribe",{"id":ident})[0],403)
                self.assertEqual(req("/api/music/analyze",{"id":ident})[0],403)
                self.assertEqual(req("/api/director",{"id":ident,"provider":"ollama"})[0],403)
                self.assertEqual(req("/api/import",{})[0],400)
                self.assertEqual(req("/api/render",{"id":ident,"clips":[0],"quality":"compact","preset":"original"})[0],403)
                self.assertEqual(req("/api/render",{"id":ident,"clips":[0],"quality":"high","preset":"landscape"})[0],403)
                self.assertEqual(ws.ledger.summary()["attempted_seconds"],0)
                self.assertEqual(req("/api/projects/delete",{"id":ident})[0],200)
            finally:
                httpd.shutdown();httpd.server_close();thread.join(timeout=5)
