import base64
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
import owner_auth
import server

class OwnerAuthTests(unittest.TestCase):
    def test_credentials_and_origin(self):
        secret="a sufficiently long test password"
        digest=owner_auth.password_digest(secret)
        self.assertTrue(owner_auth.authorized("Basic "+base64.b64encode(("owner:"+secret).encode()).decode(),digest))
        for bad in [None,"Bearer x","Basic !!","Basic "+base64.b64encode(("guest:"+secret).encode()).decode()]:
            self.assertFalse(owner_auth.authorized(bad,digest))
        with self.assertRaises(ValueError):
            owner_auth.password_digest("short")
        self.assertFalse(owner_auth.allowed_origin("http://evil.example",server.HOST))
        self.assertFalse(owner_auth.allowed_origin(None,server.HOST,"cross-site"))
        self.assertTrue(owner_auth.allowed_origin("http://"+server.HOST,server.HOST,"same-origin"))

    def test_http_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            ident="c"*32
            folder=Path(d)/ident
            folder.mkdir()
            (folder/"source.media").write_bytes(b"private")
            server.JOBS[ident]={"folder":folder}
            httpd=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
            httpd.storage=d
            httpd.persistent=False
            secret="a sufficiently long test password"
            httpd.owner_digest=owner_auth.password_digest(secret)
            thread=threading.Thread(target=httpd.serve_forever,daemon=True)
            thread.start()
            credential="Basic "+base64.b64encode(("owner:"+secret).encode()).decode()
            def request(path,auth=False,post=False,origin=None,token=True):
                conn=http.client.HTTPConnection("127.0.0.1",httpd.server_port,timeout=5)
                try:
                    headers={"Host":server.HOST}
                    if auth:
                        headers["Authorization"]=credential
                    if token:
                        headers["X-C4PCUT-Token"]=server.TOKEN
                    if origin:
                        headers["Origin"]=origin
                    conn.request("POST" if post else "GET",path,"{}" if post else None,headers)
                    response=conn.getresponse()
                    return response.status,dict(response.getheaders()),response.read()
                finally:
                    conn.close()
            try:
                self.assertEqual(request("/healthz")[0],200)
                for path in ["/","/app.js","/api/session","/api/source/"+ident]:
                    self.assertEqual(request(path)[0],401)
                self.assertEqual(request("/api/projects/list",post=True)[0],401)
                status,headers,_=request("/",auth=True)
                self.assertEqual(status,200)
                self.assertEqual(headers["X-Frame-Options"],"DENY")
                self.assertIn("frame-ancestors 'none'",headers["Content-Security-Policy"])
                self.assertEqual(request("/api/source/"+ident,auth=True)[2],b"private")
                self.assertEqual(request("/api/projects/list",auth=True,post=True,origin="https://evil.example")[0],403)
                self.assertEqual(request("/api/projects/list",auth=True,post=True,token=False)[0],403)
                self.assertEqual(request("/api/projects/list",auth=True,post=True,origin="http://"+server.HOST)[0],200)
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
                server.JOBS.pop(ident,None)
