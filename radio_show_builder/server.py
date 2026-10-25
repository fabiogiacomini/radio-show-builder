"""Loopback-only web app. All project data stays in the configured local directory."""
import argparse
import copy
import hashlib
import http.cookies
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sys
import threading
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__, audio, providers
from .documents import export_docx
from .model import ValidationError, identifier, update_project
from .store import Store
from .runtime import Instance, AlreadyRunning, open_browser, configure_frozen

STATIC = Path(__file__).with_name("static")
MAX_JSON = 2_000_000
MAX_UPLOAD = 512*1024*1024

class App(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, root, token=None):
        self.store = Store(root)
        self.token = token or secrets.token_urlsafe(32)
        self.jobs = {}
        self.guard = threading.RLock()
        self.busy = set()
        self.closing = False
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="radio-show")
        super().__init__(address, Handler)

    def job(self, pid, work):
        with self.guard:
            if self.closing:
                raise ValidationError("The app is shutting down. Reopen it to continue.")
            if pid in self.busy:
                raise ValidationError("This project already has a running task.")
            self.busy.add(pid)
            jid = uuid.uuid4().hex
            self.jobs[jid] = {"id": jid, "project_id": pid, "status": "running", "progress": 0,
                              "message": "Starting", "created": time.time()}
        def progress(value, message):
            with self.guard:
                self.jobs[jid].update(progress=value, message=message)
        def run():
            try:
                result = work(progress)
                with self.guard:
                    self.jobs[jid].update(status="done", progress=1, message="Completed", result=result)
            except ValidationError as e:
                with self.guard:
                    self.jobs[jid].update(status="error", message=str(e))
            except Exception:
                with self.guard:
                    self.jobs[jid].update(status="error", message="The task failed unexpectedly. Check available disk space and input files.")
            finally:
                with self.guard:
                    self.busy.discard(pid)
        self.executor.submit(run)
        return {"job_id": jid}

    def idle(self, pid):
        with self.guard:
            if pid in self.busy:
                raise ValidationError("Wait for the current project task to finish before changing it.")

class Handler(BaseHTTPRequestHandler):
    server_version = "RadioShowBuilder"
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt, *args):
        pass  # Avoid logging filenames, submitted text, URLs and credentials.

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; "
                         "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        super().end_headers()

    def json(self, obj, status=200, cookie=False):
        raw = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        if cookie:
            self.send_header("Set-Cookie", f"rsb_session={self.server.token}; HttpOnly; SameSite=Strict; Path=/")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def data(self):
        try:
            count = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValidationError("Invalid request size.") from None
        if not 0 < count <= MAX_JSON:
            raise ValidationError("Request is empty or too large.")
        try:
            value = json.loads(self.rfile.read(count))
        except (ValueError, UnicodeError):
            raise ValidationError("Invalid JSON request.") from None
        if not isinstance(value, dict):
            raise ValidationError("Expected a JSON object.")
        return value

    def trusted(self):
        host = self.headers.get("Host", "")
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if host not in allowed:
            return False
        origin = self.headers.get("Origin")
        return not origin or origin in {"http://"+h for h in allowed}

    def authorized(self):
        if not self.trusted():
            return False
        token = self.headers.get("X-Session-Token", "")
        if not token:
            try:
                c = http.cookies.SimpleCookie()
                c.load(self.headers.get("Cookie", ""))
                token = c["rsb_session"].value if "rsb_session" in c else ""
            except http.cookies.CookieError:
                return False
        return secrets.compare_digest(token, self.server.token)

    def file(self, path, download=None):
        path = Path(path)
        if not path.is_file():
            self.json({"error": "File not found."}, 404)
            return
        size = path.stat().st_size
        first, last = 0, size-1
        requested = self.headers.get("Range")
        status = 200
        if requested:
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
            if not m or not any(m.groups()):
                self.json({"error": "Unsupported byte range."}, 416)
                return
            if m[1]:
                first = int(m[1])
                last = min(last, int(m[2])) if m[2] else last
            else:
                first = max(0, size-int(m[2]))
            if first > last or first >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            status = 206
        self.send_response(status)
        self.send_header("Content-Type", mimetypes.guess_type(str(path))[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(last-first+1))
        if status == 206:
            self.send_header("Content-Range", f"bytes {first}-{last}/{size}")
        if download:
            safe = urllib.parse.quote(download, safe="")
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''"+safe)
        self.end_headers()
        if self.command == "HEAD":
            return
        with path.open("rb") as f:
            f.seek(first)
            remaining = last-first+1
            while remaining:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def dispatch(self):
        url = urllib.parse.urlsplit(self.path)
        parts = [urllib.parse.unquote(p) for p in url.path.strip("/").split("/") if p]
        method = "GET" if self.command == "HEAD" else self.command
        if method == "GET" and parts in ([], ["app.js"], ["style.css"]):
            if not self.trusted():
                self.json({"error": "Use the local launch URL."}, 403)
                return
            self.file(STATIC / (parts[0] if parts else "index.html"))
            return
        if not self.authorized():
            self.json({"error": "Open the launch URL printed by Radio Show Builder."}, 403)
            return
        if parts == ["api", "session"] and method == "POST":
            self.json({"ok": True, "version": __version__}, cookie=True)
            return
        if parts == ["api", "shutdown"] and method == "POST":
            with self.server.guard:
                if self.server.busy:
                    raise ValidationError("Wait for the running task to finish before quitting.")
                self.server.closing = True
            self.json({"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if parts == ["api", "config"] and method == "GET":
            try:
                binary = audio.ffmpeg()
                available = bool(binary)
            except ValidationError:
                available = False
            self.json({"providers": providers.PRESETS, "version": __version__, "ffmpeg_available": available})
            return
        if parts == ["api", "models"] and method == "POST":
            self.json({"models": providers.models(self.data())})
            return
        if parts == ["api", "projects"]:
            if method == "GET":
                self.json({"projects": self.server.store.list()})
            elif method == "POST":
                data = self.data()
                self.json(self.server.store.create(data.get("title"), data.get("preset", "podcast")), 201)
            else:
                self.json({"error": "Method not allowed."}, 405)
            return
        if len(parts) == 3 and parts[:2] == ["api", "jobs"] and method == "GET":
            identifier(parts[2])
            with self.server.guard:
                value = self.server.jobs.get(parts[2])
            self.json(value or {"error": "Job not found."}, 200 if value else 404)
            return
        if len(parts) >= 3 and parts[:2] == ["api", "projects"]:
            pid = identifier(parts[2])
            directory = self.server.store.directory(pid)
            if len(parts) == 3:
                if method == "GET":
                    self.json(self.server.store.load(pid))
                elif method == "PUT":
                    patch = self.data()
                    with self.server.store.lock(pid):
                        self.server.idle(pid)
                        current = self.server.store.load(pid)
                        p = update_project(current, patch)
                        if p != current:
                            p.pop("export", None)
                        self.server.store.save(p)
                    self.json(p)
                else:
                    self.json({"error": "Method not allowed."}, 405)
                return
            action = parts[3]
            if action == "assets" and method == "POST" and len(parts) == 4:
                self.upload(pid, url)
                return
            p = self.server.store.load(pid)
            if action == "assets" and method == "GET" and len(parts) == 5:
                asset = p["assets"].get(identifier(parts[4]))
                if not asset:
                    raise ValidationError("Audio file not found.")
                self.file(directory / "assets" / asset["file"])
                return
            if action == "analyse" and method == "GET":
                self.json(audio.analyse(p))
                return
            if action == "script.docx" and method == "GET":
                export_docx(p, directory / "script.docx")
                self.file(directory / "script.docx", "radio-show-script.docx")
                return
            if action == "project.json" and method == "GET":
                # Portable script/settings only; binary audio is deliberately not embedded.
                portable = copy.deepcopy(p)
                portable["assets"] = {}
                portable["jingle_id"] = None
                portable.pop("export", None)
                for e in portable["entries"]:
                    e["asset_id"] = None
                self.json(portable)
                return
            if action == "generate" and method == "POST":
                data = self.data()
                if p["entries"] and not data.get("replace_existing"):
                    raise ValidationError("Confirm replacing the current draft before generating again.")
                def work(progress):
                    progress(.1, "Writing the draft with your selected AI")
                    draft = providers.generate(p, data.get("provider", {}), data.get("music_percent"))
                    with self.server.store.lock(pid):
                        updated = self.server.store.load(pid)
                        updated.update(draft)
                        updated.pop("export", None)
                        self.server.store.save(updated)
                    return {"title": draft["title"]}
                self.json(self.server.job(pid, work), 202)
                return
            if action == "render" and method == "POST":
                def work(progress):
                    report = audio.render(copy.deepcopy(p), directory, progress)
                    with self.server.store.lock(pid):
                        updated = self.server.store.load(pid)
                        updated["export"] = {"duration_seconds": report["duration_seconds"],
                                             "bitrate_kbps": report["bitrate_kbps"],
                                             "integrated_lufs": report["integrated_lufs"],
                                             "true_peak_db": report["true_peak_db"]}
                        self.server.store.save(updated)
                    return updated["export"]
                self.json(self.server.job(pid, work), 202)
                return
            if action == "exports" and method == "GET" and len(parts) == 5:
                if not p.get("export"):
                    raise ValidationError("Render the current project before downloading an export.")
                filename = parts[4]
                if filename not in ("show.mp3", "report.json", "rundown.txt"):
                    raise ValidationError("Unknown export.")
                self.file(directory / "exports" / filename,
                          None if filename == "show.mp3" and "preview" in urllib.parse.parse_qs(url.query) else filename)
                return
        self.json({"error": "Not found."}, 404)

    def upload(self, pid, url):
        query = urllib.parse.parse_qs(url.query)
        filename = Path(query.get("filename", ["audio.mp3"])[0]).name[:200]
        suffix = Path(filename).suffix.lower()
        if suffix not in (".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"):
            raise ValidationError("Upload MP3, WAV, FLAC, M4A, OGG or AAC audio.")
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValidationError("Invalid upload size.") from None
        if not 0 < size <= MAX_UPLOAD:
            raise ValidationError("Each audio upload must be smaller than 512 MiB.")
        aid = uuid.uuid4().hex
        directory = self.server.store.directory(pid) / "assets"
        directory.mkdir(exist_ok=True)
        path = directory / (aid+suffix)
        digest = hashlib.sha256()
        try:
            with path.open("wb") as f:
                remaining = size
                while remaining:
                    chunk = self.rfile.read(min(1024*1024, remaining))
                    if not chunk:
                        raise ValidationError("Upload was interrupted.")
                    f.write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)
            duration = audio.probe(path)
            asset = {"id": aid, "name": filename, "file": path.name,
                     "sha256": digest.hexdigest(), "duration_seconds": duration, "bytes": size}
            with self.server.store.lock(pid):
                self.server.idle(pid)
                p = self.server.store.load(pid)
                p["assets"][aid] = asset
                self.server.store.save(p)
            self.json(asset, 201)
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def handle_request(self):
        try:
            self.dispatch()
        except ValidationError as e:
            self.json({"error": str(e)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self.json({"error": "The request failed. Check available disk space and try again."}, 500)

    do_GET = do_HEAD = do_POST = do_PUT = handle_request

def main():
    parser = argparse.ArgumentParser(description="Run Radio Show Builder locally.")
    parser.add_argument("--port", type=int, default=0 if getattr(sys, "frozen", False) else 8765)
    parser.add_argument("--data-dir", default=os.environ.get("RSB_DATA_DIR", str(Path.home()/".radio-show-builder")))
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--self-test-report", metavar="PATH", help="Run offline package diagnostics and write a JSON report.")
    args = parser.parse_args()
    args.data_dir = str(Path(args.data_dir).expanduser().resolve())
    configure_frozen()
    if args.self_test_report:
        from .diagnostics import self_test
        self_test(Path(args.self_test_report))
        return
    try:
        with Instance(args.data_dir) as instance:
            try:
                app = App(("127.0.0.1", args.port), args.data_dir)
            except OSError as e:
                parser.exit(1, f"Could not start the local server: {e}\n")
            url = f"http://127.0.0.1:{app.server_port}/#token={app.token}"
            instance.set_url(url)
            if sys.stdout is not None:
                print(f"Radio Show Builder {__version__}\nOpen: {url}\nUse Quit app in the browser to stop.", flush=True)
            if not args.no_browser:
                open_browser(url)
            try:
                app.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                app.server_close()
                app.executor.shutdown(wait=True, cancel_futures=True)
    except AlreadyRunning:
        url_file = Path(args.data_dir).expanduser() / "launch-url.txt"
        for _ in range(20):
            try:
                url = url_file.read_text().strip()
                if re.fullmatch(r"http://127\.0\.0\.1:\d+/#token=[A-Za-z0-9_-]+", url):
                    if not args.no_browser:
                        open_browser(url)
                    if sys.stdout is not None:
                        print("Radio Show Builder is already running. Open: " + url)
                    return
            except OSError:
                pass
            time.sleep(.1)
        parser.exit(1, "Radio Show Builder is already starting. Try opening it again shortly.\n")

if __name__ == "__main__":
    main()
