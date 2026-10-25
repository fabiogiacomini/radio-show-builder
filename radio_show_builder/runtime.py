"""Paths and subprocess settings shared by source and portable distributions."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


def configure_frozen():
    if not getattr(sys, "frozen", False):
        return
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetDllDirectoryW(None)


class AlreadyRunning(Exception):
    pass


class Instance:
    """Keep one process per data directory, including after a second double-click."""
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.url_file = self.root / "launch-url.txt"
        self.lock = None

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = (self.root / ".instance.lock").open("a+b")
        self.lock.seek(0, 2)
        if self.lock.tell() == 0:
            self.lock.write(b"0")
            self.lock.flush()
        self.lock.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            self.lock = None
            raise AlreadyRunning() from None
        return self

    def set_url(self, url):
        with self.url_file.open("w", encoding="utf-8") as f:
            self.url_file.chmod(0o600)
            f.write(url + "\n")

    def __exit__(self, *args):
        self.url_file.unlink(missing_ok=True)
        if self.lock:
            self.lock.close()


def open_browser(url):
    import webbrowser
    # No worker threads are serving requests yet. Restore the OS environment
    # only while the browser launcher runs, then leave the bundle untouched.
    original = os.environ.get("LD_LIBRARY_PATH")
    if getattr(sys, "frozen", False) and sys.platform.startswith("linux"):
        replacement = os.environ.get("LD_LIBRARY_PATH_ORIG")
        if replacement is None:
            os.environ.pop("LD_LIBRARY_PATH", None)
        else:
            os.environ["LD_LIBRARY_PATH"] = replacement
    try:
        return webbrowser.open(url)
    finally:
        if original is None:
            os.environ.pop("LD_LIBRARY_PATH", None)
        else:
            os.environ["LD_LIBRARY_PATH"] = original


def ffmpeg_path():
    override = os.environ.get("RSB_FFMPEG")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        bundled = Path(sys._MEIPASS) / "bin" / name
        if bundled.is_file():
            return bundled
    found = shutil.which("ffmpeg")
    return Path(found) if found else None


def process_options():
    options = {}
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    if getattr(sys, "frozen", False) and sys.platform.startswith("linux"):
        env = os.environ.copy()
        original = env.get("LD_LIBRARY_PATH_ORIG")
        if original is None:
            env.pop("LD_LIBRARY_PATH", None)
        else:
            env["LD_LIBRARY_PATH"] = original
        options["env"] = env
    return options
