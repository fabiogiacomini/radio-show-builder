"""Download exact audio-engine sources; never execute an unverified archive."""
import hashlib
import json
from pathlib import Path
import urllib.request

root = Path(__file__).resolve().parents[1]
destination = root / "build" / "sources"
destination.mkdir(parents=True, exist_ok=True)
for source in json.loads((root / "packaging" / "sources.json").read_text()):
    target = destination / source["name"]
    if not target.exists():
        with urllib.request.urlopen(source["url"], timeout=120) as response:
            target.write_bytes(response.read())
    if hashlib.sha256(target.read_bytes()).hexdigest() != source["sha256"]:
        raise RuntimeError("Source checksum mismatch: " + source["name"])
    print("Verified " + source["name"])
