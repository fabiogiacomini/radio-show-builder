"""Validation and portable project records. Credentials never belong in a project."""
import math
import re
import uuid

ID = re.compile(r"^[a-f0-9]{32}$")
KINDS = {"speech", "music"}
DEFAULT_SETTINGS = {
    "duration_mode": "exact", "target_seconds": 5400.0,
    "bitrate_kbps": 192, "sample_rate": 48000,
    "music_lufs": -16.0, "speech_lufs": -17.0, "true_peak_db": -1.5,
    "bed_db": -27.0, "crossfade_seconds": 3.0,
    "intro_seconds": 12.0, "outro_seconds": 12.0,
}

class ValidationError(ValueError):
    pass

def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValidationError("Invalid identifier.")
    return value

def number(value, low, high, label):
    if isinstance(value, bool):
        raise ValidationError(label + " must be a number.")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValidationError(label + " must be a number.") from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValidationError(f"{label} must be between {low} and {high}.")
    return value

def text(value, limit=20000):
    if not isinstance(value, str) or len(value) > limit:
        raise ValidationError("Invalid or excessively long text.")
    return value

def settings(value=None):
    if value is not None and not isinstance(value, dict):
        raise ValidationError("Settings must be an object.")
    s = {**DEFAULT_SETTINGS, **(value or {})}
    if s["duration_mode"] not in ("exact", "natural"):
        raise ValidationError("Choose exact or natural duration.")
    out = {
        "duration_mode": s["duration_mode"],
        "target_seconds": number(s["target_seconds"], 1, 14400, "Target duration"),
        "bed_db": number(s["bed_db"], -50, -12, "Background attenuation"),
        "music_lufs": number(s["music_lufs"], -24, -12, "Music loudness"),
        "speech_lufs": number(s["speech_lufs"], -24, -12, "Speech loudness"),
        "true_peak_db": number(s["true_peak_db"], -6, -1, "True peak"),
        "crossfade_seconds": number(s["crossfade_seconds"], 0, 12, "Crossfade"),
        "intro_seconds": number(s["intro_seconds"], 0, 120, "Opening jingle"),
        "outro_seconds": number(s["outro_seconds"], 0, 120, "Closing jingle"),
    }
    for key, choices in [("bitrate_kbps", (128, 192, 256, 320)),
                         ("sample_rate", (44100, 48000))]:
        if s[key] not in choices:
            raise ValidationError(f"Unsupported {key}.")
        out[key] = int(s[key])
    return out

def entries(value, assets=None):
    if not isinstance(value, list) or len(value) > 160:
        raise ValidationError("A rundown must contain at most 160 segments.")
    result, seen = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise ValidationError("Each segment must be an object.")
        eid = identifier(item.get("id") or uuid.uuid4().hex)
        if eid in seen:
            raise ValidationError("Segment identifiers must be unique.")
        seen.add(eid)
        kind = item.get("kind", "speech")
        if kind not in KINDS:
            raise ValidationError("Segment type must be speech or music.")
        aid = item.get("asset_id") or None
        if aid:
            identifier(aid)
            if assets is not None and aid not in assets:
                raise ValidationError("A segment references an unknown audio file.")
        end = item.get("trim_end")
        start = number(item.get("trim_start", 0), 0, 86400, "Trim start")
        if end in (None, ""):
            end = None
        else:
            end = number(end, start + .01, 86400, "Trim end")
        result.append({
            "id": eid, "kind": kind, "title": text(item.get("title", ""), 500),
            "text": text(item.get("text", "")), "notes": text(item.get("notes", "")),
            "estimated_seconds": number(item.get("estimated_seconds", 60), .01, 86400, "Estimated duration"),
            "asset_id": aid, "trim_start": start, "trim_end": end,
        })
    return result

def new_project(title="Untitled show"):
    return {
        "schema_version": 1, "id": uuid.uuid4().hex, "title": text(title, 200),
        "idea": "", "language": "English",
        "tone": "Informative, friendly and conversational, with natural pauses.",
        "research_notes": "", "verification_notes": "",
        "entries": [], "assets": {}, "jingle_id": None, "settings": settings(),
    }

def update_project(current, patch):
    if not isinstance(patch, dict):
        raise ValidationError("A project must be an object.")
    out = dict(current)
    for key, limit in [("title", 200), ("idea", 10000), ("language", 100),
                       ("tone", 2000), ("research_notes", 30000), ("verification_notes", 10000)]:
        if key in patch:
            out[key] = text(patch[key], limit)
    if "entries" in patch:
        out["entries"] = entries(patch["entries"], current["assets"])
    if "settings" in patch:
        out["settings"] = settings(patch["settings"])
    if "jingle_id" in patch:
        aid = patch["jingle_id"] or None
        if aid and identifier(aid) not in current["assets"]:
            raise ValidationError("Unknown jingle file.")
        out["jingle_id"] = aid
    return out
