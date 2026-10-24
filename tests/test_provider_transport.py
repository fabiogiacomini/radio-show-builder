from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest
from radio_show_builder import providers
from radio_show_builder.model import ValidationError, new_project

class ProviderTransportTests(unittest.TestCase):
    def setUp(self):
        self.received=[]
        received=self.received
        class Fake(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                self.send_response(200);self.end_headers()
                self.wfile.write(json.dumps({"data":[{"id":"example-text-model"}]}).encode())
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                received.append((self.path,dict(self.headers),body))
                if self.path.startswith("/redirect"):
                    self.send_response(302)
                    self.send_header("Location",f"http://127.0.0.1:{self.server.server_port}/should-not-be-called")
                    self.end_headers()
                    return
                draft=json.dumps({"title":"A test programme","verification_notes":"","entries":[{"kind":"speech","text":"Hello."}]})
                if self.path.endswith("/messages"):
                    data={"content":[{"type":"text","text":draft}]}
                elif self.path.endswith("/responses"):
                    data={"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":draft}]}]}
                else:
                    data={"choices":[{"message":{"content":draft},"finish_reason":"stop"}]}
                self.send_response(200);self.end_headers();self.wfile.write(json.dumps(data).encode())
        self.server=ThreadingHTTPServer(("127.0.0.1",0),Fake)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.base=f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown();self.server.server_close()

    def test_real_http_for_all_protocols_and_catalogue(self):
        p=new_project("Transport test")
        p["idea"]="A short test brief"
        for protocol in ("chat","responses","anthropic"):
            c={"provider":"custom","protocol":protocol,"base_url":self.base+"/v1",
               "model":"example-text-model","api_key":"local-test-key"}
            result=providers.generate(p,c)
            self.assertEqual(result["title"],"A test programme")
            self.assertEqual(providers.models(c),["example-text-model"])
        self.assertEqual(len(self.received),3)
        self.assertEqual(self.received[2][1]["X-Api-Key"],"local-test-key")

    def test_redirect_does_not_forward_credentials(self):
        c={"provider":"custom","protocol":"chat","base_url":self.base+"/redirect",
           "model":"example-text-model","api_key":"local-test-key"}
        with self.assertRaises(ValidationError):
            providers.generate(new_project(),c)
        self.assertEqual(len(self.received),1)
