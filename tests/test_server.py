import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from radio_show_builder.server import App

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = App(("127.0.0.1",0), self.tmp.name, token="test-session-only")
        self.thread = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.app.server_port

    def tearDown(self):
        self.app.shutdown()
        self.app.server_close()
        self.app.executor.shutdown(wait=True)
        self.tmp.cleanup()

    def req(self, method, path, body=None, auth=True, extra=None):
        c = http.client.HTTPConnection("127.0.0.1",self.port,timeout=10)
        headers = {"X-Session-Token":"test-session-only"} if auth else {}
        headers.update(extra or {})
        if body is not None:
            body = json.dumps(body)
            headers["Content-Type"]="application/json"
        c.request(method,path,body,headers)
        r = c.getresponse()
        status, data, headers = r.status,r.read(),dict(r.getheaders())
        c.close()
        return status,data,headers

    def test_private_api_and_origin_validation(self):
        self.assertEqual(self.req("GET","/api/projects",auth=False)[0],403)
        self.assertEqual(self.req("GET","/api/projects",extra={"Origin":"https://example.com"})[0],403)
        self.assertEqual(self.req("GET","/api/projects",extra={"Host":"evil.example"})[0],403)
        status,raw,headers = self.req("POST","/api/session")
        self.assertEqual(status,200)
        self.assertIn("HttpOnly",headers["Set-Cookie"])
        self.assertIn("SameSite=Strict",headers["Set-Cookie"])

    def test_project_and_portable_export(self):
        status,raw,_ = self.req("POST","/api/projects",{"title":"Local test"})
        self.assertEqual(status,201)
        p = json.loads(raw)
        base = "/api/projects/"+p["id"]
        status,raw,_ = self.req("PUT",base,{"api_key":"not-a-real-key","entries":[{"kind":"speech","text":"Hello."}]})
        self.assertEqual(status,200)
        saved=json.loads(raw)
        self.assertNotIn("not-a-real-key",json.dumps(saved))
        self.assertEqual(self.req("GET",base+"/project.json")[0],200)
        self.assertEqual(self.req("GET","/api/projects/../../etc/passwd")[0],400)

    def test_binary_range_and_security_headers(self):
        p = self.app.store.create("Range test")
        aid = "a"*32
        root = self.app.store.directory(p["id"])/"assets"
        root.mkdir()
        (root/(aid+".mp3")).write_bytes(b"0123456789")
        p["assets"][aid]={"file":aid+".mp3"}
        self.app.store.save(p)
        path = "/api/projects/"+p["id"]+"/assets/"+aid
        status,raw,headers = self.req("GET",path,extra={"Range":"bytes=2-5"})
        self.assertEqual((status,raw),(206,b"2345"))
        self.assertEqual(headers["Content-Range"],"bytes 2-5/10")
        self.assertIn("frame-ancestors 'none'",headers["Content-Security-Policy"])

    def test_project_locked_during_job(self):
        p=self.app.store.create("Busy project")
        event=threading.Event()
        self.app.job(p["id"], lambda progress: event.wait(5))
        try:
            self.assertEqual(self.req("PUT","/api/projects/"+p["id"],{"title":"Changed"})[0],400)
        finally:
            event.set()
