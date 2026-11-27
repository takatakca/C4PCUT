import base64
import hmac
import json
import secrets
import tempfile
import threading
import unittest
import http.client
from pathlib import Path
from http.server import ThreadingHTTPServer
import studio_gateway
import owner_auth
import server
import workspaces

A="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
B="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
PROFILE="cccccccc-cccc-cccc-cccc-cccccccccccc"
KEY=b"k"*32

def encode(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")

def assertion(target="/api/session",method="GET",client=A,**changes):
    claims={"iss":studio_gateway.ISSUER,"aud":studio_gateway.AUDIENCE,"sub":PROFILE,
            "client_id":client,"permission":"create_content","entitlement":"c4pcut_active",
            "iat":1000,"exp":1030,"nonce":secrets.token_hex(16),"method":method,"target":target}
    claims.update(changes)
    raw=encode(json.dumps(claims,separators=(",",":")).encode())
    return raw+"."+encode(hmac.digest(KEY,raw.encode(),"sha256"))

class GatewayTests(unittest.TestCase):
    def test_signature_scope_expiry_replay(self):
        g=studio_gateway.Gateway(KEY,{A:"alpha",B:"beta"},{"alpha":None,"beta":None},clock=lambda:1001)
        token=assertion()
        self.assertEqual(g.verify(token,"GET","/api/session").workspace,"alpha")
        self.assertIsNone(g.verify(token,"GET","/api/session"))
        for kw in [{"exp":1001},{"iat":1002},{"exp":1031},{"aud":"wrong"},{"permission":"view_reports"},{"entitlement":"inactive"},{"client":"dddddddd-dddd-dddd-dddd-dddddddddddd"},{"sub":"bad"},{"method":"POST"},{"target":"/api/usage"}]:
            self.assertIsNone(g.verify(assertion(**kw),"GET","/api/session"))
        token=assertion()
        raw,sig=token.split(".")
        self.assertIsNone(g.verify(raw+"."+encode(b"x"*32),"GET","/api/session"))
        self.assertIsNone(g.verify(assertion(target="/api/session?x=1"),"GET","/api/session"))
        with self.assertRaises(ValueError):
            studio_gateway.Gateway(KEY,{A:"alpha",B:"alpha"},{"alpha":None,"beta":None})

    def test_http_scope_and_no_basic_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            cfg=root/"config.json"
            password="private workspace password 123"
            cfg.write_text(json.dumps({s:{"password_sha256":owner_auth.password_digest(password).hex()} for s in ("alpha","beta")}))
            registry=workspaces.load(cfg,root)
            ident="a"*32
            folder=registry["alpha"].storage/ident
            folder.mkdir()
            (folder/"source.media").write_bytes(b"private alpha")
            registry["alpha"].jobs[ident]={"folder":folder}
            httpd=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
            httpd.workspaces=registry
            httpd.persistent=True
            httpd.studio_gateway=studio_gateway.Gateway(KEY,{A:"alpha",B:"beta"},registry,clock=lambda:1001)
            thread=threading.Thread(target=httpd.serve_forever,daemon=True)
            thread.start()
            def req(path,token=None,basic=False,payload=None,csrf=None):
                headers={"Host":server.HOST}
                if token:headers["X-C4PCUT-Gateway"]=token
                if basic:headers["Authorization"]="Basic "+base64.b64encode(("alpha:"+password).encode()).decode()
                if csrf:headers["X-C4PCUT-Token"]=csrf
                conn=http.client.HTTPConnection("127.0.0.1",httpd.server_port,timeout=5)
                try:
                    conn.request("POST" if payload is not None else "GET",path,json.dumps(payload) if payload is not None else None,headers)
                    response=conn.getresponse()
                    return response.status,response.read()
                finally:conn.close()
            try:
                self.assertEqual(req("/healthz")[0],200)
                self.assertEqual(req("/api/session",basic=True)[0],401)
                token=assertion()
                status,raw=req("/api/session",token)
                self.assertEqual(status,200)
                self.assertEqual(json.loads(raw)["workspace"],"alpha")
                self.assertEqual(req("/api/session",token)[0],401)
                path="/api/source/"+ident
                self.assertEqual(req(path,assertion(target=path)),(200,b"private alpha"))
                self.assertEqual(req(path,assertion(target=path,client=B))[0],404)
                path="/api/projects/list"
                self.assertEqual(req(path,assertion(target=path,method="POST",client=B),payload={},csrf=registry["alpha"].token)[0],403)
                self.assertEqual(req(path,assertion(target=path,method="POST",client=B),payload={},csrf=registry["beta"].token)[0],200)
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
