import base64
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import server
import workspaces
import owner_auth
import engine
from render_queue import RenderQueue, Cancelled

class WorkspaceTests(unittest.TestCase):
    def test_scope_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            secrets={"alpha":"alpha private long secret 123","beta":"beta private long secret 456"}
            config=root/"config.json"
            config.write_text(json.dumps({k:{"password_sha256":owner_auth.password_digest(v).hex(),"monthly_render_seconds":10 if k=="alpha" else 20} for k,v in secrets.items()}))
            registry=workspaces.load(config,root)
            a,b="a"*32,"b"*32
            for slug,ident in (("alpha",a),("beta",b)):
                ws=registry[slug]
                folder=ws.storage/ident
                folder.mkdir()
                (folder/"source.media").write_bytes(slug.encode())
                ws.jobs[ident]={"folder":folder,"metadata":{"duration":4,"width":160,"height":120,"audio":False},"clips":engine.segments(4,[2])}
            httpd=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
            httpd.storage=root
            httpd.persistent=True
            httpd.workspaces=registry
            thread=threading.Thread(target=httpd.serve_forever,daemon=True)
            thread.start()
            q=RenderQueue()
            def request(slug,path,payload=None,token=None,password=None):
                conn=http.client.HTTPConnection("127.0.0.1",httpd.server_port,timeout=5)
                try:
                    headers={"Host":server.HOST}
                    if slug:
                        auth=slug+":"+(password if password is not None else secrets[slug])
                        headers["Authorization"]="Basic "+base64.b64encode(auth.encode()).decode()
                    if payload is not None:
                        headers["Content-Type"]="application/json"
                        headers["X-C4PCUT-Token"]=token if token is not None else registry[slug].token
                    conn.request("POST" if payload is not None else "GET",path,json.dumps(payload) if payload is not None else None,headers)
                    res=conn.getresponse()
                    return res.status,res.read()
                finally:
                    conn.close()
            try:
                self.assertEqual(request(None,"/api/session")[0],401)
                self.assertEqual(request("alpha","/api/session",password=secrets["beta"])[0],401)
                self.assertEqual(json.loads(request("alpha","/api/session")[1])["workspace"],"alpha")
                self.assertNotEqual(registry["alpha"].token,registry["beta"].token)
                self.assertEqual(request("alpha","/api/source/"+a),(200,b"alpha"))
                self.assertEqual(request("beta","/api/source/"+a)[0],404)
                for path in ("/api/export/","/api/captions/","/api/thumbnail/"):
                    self.assertEqual(request("beta",path+a+("/0.jpg" if "thumbnail" in path else ""))[0],404)
                self.assertEqual(request("beta","/api/projects/save",{"id":a,"name":"Stolen"})[0],400)
                self.assertEqual(request("beta","/api/media/list",{"id":a})[0],400)
                self.assertEqual(request("beta","/api/media/remove",{"id":a,"kind":"logo"})[0],400)
                self.assertEqual(request("alpha","/api/media/remove",{"id":a,"kind":"logo"},token=registry["beta"].token)[0],403)
                self.assertEqual(request("alpha","/api/media/remove",{"id":a,"kind":"../source.media"})[0],400)
                self.assertEqual(request("alpha","/api/media/list",{"id":a})[0],200)
                self.assertEqual(request("alpha","/api/media/remove",{"id":a,"kind":"logo"})[0],200)
                self.assertEqual(request("beta","/api/projects/open",{"id":a})[0],400)
                self.assertEqual(request("beta","/api/projects/delete",{"id":a})[0],400)
                original=engine.segments(4,[2]);replacement=engine.segments(4,[1,2])
                layout={"id":a,"expected":original,"clips":replacement}
                self.assertEqual(request("beta","/api/scenes/restore",layout)[0],400)
                self.assertEqual(request("alpha","/api/scenes/restore",layout,token=registry["beta"].token)[0],403)
                self.assertEqual(request("alpha","/api/scenes/restore",layout)[0],200)
                self.assertEqual(request("alpha","/api/scenes/restore",layout)[0],400)
                self.assertEqual(registry["alpha"].jobs[a]["clips"],replacement)
                self.assertEqual(request("alpha","/api/scenes/restore",{"id":a,"expected":replacement,"clips":original})[0],200)
                pack={"studio":"TAKATAKSTUDIO","version":1,"kind":"production_request_pack","project":{"title":"Alpha brief","brief":"Edit a video","audience":"Music fans","language":"en","clientId":"beta"},"characters":[],"jobs":[{"command":"not authorized"}]}
                code,raw=request("alpha","/api/studio/import-pack",pack)
                self.assertEqual(code,200)
                brief=json.loads(raw)["brief"]
                self.assertNotIn("clientId",brief)
                self.assertEqual(request("alpha","/api/projects/save",{"id":a,"name":"Alpha","selected":[0],"studio_brief":brief})[0],200)
                code,raw=request("alpha","/api/projects/open",{"id":a})
                self.assertEqual(code,200)
                self.assertEqual(json.loads(raw)["state"]["studio_brief"],brief)
                self.assertIn("Alpha brief",json.loads(raw)["director_prompt"])
                self.assertEqual(request("beta","/api/projects/open",{"id":a})[0],400)
                self.assertEqual([x["id"] for x in json.loads(request("beta","/api/projects/list",{})[1])["projects"]],[b])
                self.assertEqual(request("beta","/api/projects/list",{},token=registry["alpha"].token)[0],403)
                registry["alpha"].ledger.reserve(a,"main",3)
                self.assertEqual(json.loads(request("beta","/api/usage")[1])["attempted_seconds"],0)
                self.assertEqual(json.loads(request("alpha","/api/usage")[1])["attempted_seconds"],3)
                started=threading.Event()
                def work(cancel,progress):
                    started.set()
                    if cancel.wait(3):
                        raise Cancelled()
                    return {}
                with patch.object(server,"RENDERS",q):
                    task=q.submit(a,work,scope="alpha")
                    self.assertTrue(started.wait(2))
                    self.assertEqual(request("beta","/api/render/status",{"render_id":task})[0],400)
                    self.assertEqual(request("beta","/api/render/cancel",{"render_id":task})[0],400)
                    self.assertEqual(request("alpha","/api/render/status",{"render_id":task})[0],200)
                    self.assertEqual(request("alpha","/api/render/cancel",{"render_id":task})[0],200)
                self.assertTrue((registry["alpha"].storage/a/"source.media").exists())
            finally:
                q.shutdown()
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
    def test_config_rejects_bad_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cfg=root/"config.json"
            for name in ("../escape","owner","a/b"):
                cfg.write_text(json.dumps({name:{"password_sha256":"a"*64}}))
                with self.assertRaises(ValueError):
                    workspaces.load(cfg,root)
