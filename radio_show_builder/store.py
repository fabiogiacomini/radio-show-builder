"""Small local store with atomic writes and per-project locks."""
import json
from pathlib import Path
import threading
from .model import identifier, new_project, ValidationError

class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.root.chmod(0o700)
        self._lock = threading.RLock()
        self._locks = {}

    def lock(self, pid):
        identifier(pid)
        with self._lock:
            return self._locks.setdefault(pid, threading.RLock())

    def directory(self, pid):
        return self.root / identifier(pid)

    def load(self, pid):
        with self.lock(pid):
            try:
                return json.loads((self.directory(pid) / "project.json").read_text("utf-8"))
            except FileNotFoundError:
                raise ValidationError("Project not found.") from None

    def save(self, project):
        pid = project["id"]
        with self.lock(pid):
            path = self.directory(pid)
            path.mkdir(exist_ok=True)
            temp = path / "project.tmp"
            temp.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(path / "project.json")

    def create(self, title=None, preset="podcast"):
        p = new_project(title, preset)
        self.save(p)
        return p

    def list(self):
        rows = []
        for f in self.root.glob("*/project.json"):
            try:
                p = json.loads(f.read_text("utf-8"))
                rows.append({"id": p["id"], "title": p["title"], "updated": f.stat().st_mtime})
            except (OSError, ValueError, KeyError):
                continue
        return sorted(rows, key=lambda x: x["updated"], reverse=True)
