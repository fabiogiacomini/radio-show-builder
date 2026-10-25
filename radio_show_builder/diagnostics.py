"""Offline, end-to-end checks run inside each frozen release executable."""
import hashlib
import http.client
import io
import json
from pathlib import Path
import platform
import ssl
import tempfile
import threading
import time
import wave
from zipfile import ZipFile

import numpy as np

from . import __version__, audio


def self_test(report_path):
    from .server import App
    report = {"version": __version__, "system": platform.system(), "machine": platform.machine(), "ok": False}
    try:
        assert ssl.create_default_context().get_ca_certs(), "HTTPS certificate store is empty"
        with tempfile.TemporaryDirectory(prefix="rsb-check-") as tmp:
            app = App(("127.0.0.1", 0), Path(tmp) / "shows")
            thread = threading.Thread(target=app.serve_forever, daemon=True)
            thread.start()
            def request(method, path, body=None, content_type="application/json", auth=True):
                conn = http.client.HTTPConnection("127.0.0.1", app.server_port, timeout=30)
                headers = {"Content-Type": content_type}
                if auth:
                    headers["X-Session-Token"] = app.token
                if isinstance(body, dict):
                    body = json.dumps(body).encode()
                conn.request(method, path, body, headers)
                response = conn.getresponse()
                status, raw = response.status, response.read()
                conn.close()
                return status, raw
            def api(method, path, body=None):
                status, raw = request(method, path, body)
                if not 200 <= status < 300:
                    raise RuntimeError(f"Package diagnostic failed at {path}: HTTP {status}")
                return json.loads(raw)
            try:
                status, html = request("GET", "/", auth=False)
                assert status == 200 and b"Fabio Giacomini" in html
                for path in ["/app.js", "/style.css"]:
                    assert request("GET", path, auth=False)[0] == 200
                assert request("GET", "/api/projects", auth=False)[0] == 403
                config = api("GET", "/api/config")
                assert config["ffmpeg_available"] and config["version"] == __version__
                project = api("POST", "/api/projects", {"title": "Offline package check"})
                base = "/api/projects/" + project["id"]
                sources, segments = {}, []
                for index, (kind, duration, frequency) in enumerate([("speech", 2, 220), ("music", 3, 440), ("music", 3, 660), ("speech", 2, 250), ("jingle", 4, 110)]):
                    t = np.arange(duration * 48000) / 48000
                    mono = .15 * np.sin(2 * np.pi * frequency * t) + .025 * np.sin(2 * np.pi * frequency * 1.51 * t)
                    samples = np.rint(np.column_stack([mono, mono * .9]) * 32767).astype("<i2").tobytes()
                    out = io.BytesIO()
                    with wave.open(out, "wb") as w:
                        w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000); w.writeframes(samples)
                    blob = out.getvalue()
                    status, raw = request("POST", base + f"/assets?filename=signal-{index}.wav", blob, "application/octet-stream")
                    assert status == 201
                    asset = json.loads(raw)
                    sources[asset["id"]] = hashlib.sha256(blob).hexdigest()
                    if kind == "jingle":
                        jingle = asset["id"]
                    else:
                        segments.append({"kind": kind, "title": "Generated " + kind, "text": "A package test." if kind == "speech" else "", "asset_id": asset["id"]})
                api("PUT", base, {"entries": segments, "jingle_id": jingle, "settings": {"target_seconds": 14, "intro_seconds": 1, "outro_seconds": 1, "crossfade_seconds": .5}})
                status, doc = request("GET", base + "/script.docx")
                assert status == 200
                with ZipFile(io.BytesIO(doc)) as z:
                    assert b"A package test." in z.read("word/document.xml")
                job = api("POST", base + "/render", {})
                deadline = time.monotonic() + 240
                while time.monotonic() < deadline:
                    state = api("GET", "/api/jobs/" + job["job_id"])
                    if state["status"] != "running":
                        break
                    time.sleep(.2)
                assert state["status"] == "done", state.get("message")
                result = api("GET", base + "/exports/report.json")
                assert result["duration_seconds"] == 14 and result["bitrate_kbps"] == 192
                assert result["checks_passed"] and result["decoded_sample_count_verified"] and result["within_peak_ceiling"]
                assert request("GET", base + "/exports/show.mp3")[0] == 200
                for aid, digest in sources.items():
                    assert hashlib.sha256(request("GET", base + "/assets/" + aid)[1]).hexdigest() == digest
                api("POST", "/api/shutdown")
                thread.join(5)
                assert not thread.is_alive()
                report.update(ok=True, checks=["HTTPS trust store", "static interface", "private API", "audio upload", "Word export", "jingle bed", "crossfade", "14-second render", "192 kbps CBR", "decoded sample count", "peak ceiling", "unchanged originals", "clean shutdown"], audio=result, ffmpeg=Path(audio.ffmpeg()).name)
            finally:
                app.shutdown()
                app.server_close()
                app.executor.shutdown(wait=True, cancel_futures=True)
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
