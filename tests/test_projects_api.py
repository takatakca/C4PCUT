import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
import server

class ProjectsAPITests(unittest.TestCase):
    def test_save_reopen_and_delete(self):
        with tempfile.TemporaryDirectory() as d:
            project_id="a"*32
            folder=Path(d)/project_id
            folder.mkdir()
            (folder/"source.media").write_bytes(b"test media")
            server.JOBS[project_id]={"folder":folder,"metadata":{"duration":4,"width":160,"height":120,"audio":False},"clips":[{"id":0,"start":0,"end":4}]}
            httpd=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
            httpd.storage=d
            httpd.persistent=True
            thread=threading.Thread(target=httpd.serve_forever,daemon=True)
            thread.start()
            def request(path,payload=None):
                conn=http.client.HTTPConnection("127.0.0.1",httpd.server_port,timeout=5)
                try:
                    headers={"Host":server.HOST,"X-C4PCUT-Token":server.TOKEN}
                    if payload is None:
                        conn.request("GET",path,headers=headers)
                    else:
                        headers["Content-Type"]="application/json"
                        conn.request("POST",path,json.dumps(payload),headers)
                    response=conn.getresponse()
                    return response.status,response.read()
                finally:
                    conn.close()
            try:
                status,_=request("/api/projects/save",{"id":project_id,"name":"Saved project","selected":[0],"source_mime":"video/webm","edits":{"0":{"start":1,"end":3,"effect":"warm"}}})
                self.assertEqual(status,200)
                server.JOBS.pop(project_id)
                status,raw=request("/api/projects/list",{})
                self.assertEqual(status,200)
                self.assertTrue(json.loads(raw)["projects"][0]["saved"])
                status,raw=request("/api/projects/open",{"id":project_id})
                self.assertEqual(status,200)
                opened=json.loads(raw)
                self.assertEqual(opened["state"]["source_mime"],"video/webm")
                self.assertEqual(opened["state"]["edits"]["0"]["start"],1)
                self.assertEqual(request(opened["source_url"]),(200,b"test media"))
                self.assertEqual(request("/api/projects/delete",{"id":"../"})[0],400)
                self.assertEqual(request("/api/projects/delete",{"id":project_id})[0],200)
                self.assertFalse(folder.exists())
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
                server.JOBS.pop(project_id,None)
