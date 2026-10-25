"""Local loudness normalisation, sample-accurate assembly and MP3 verification."""
from pathlib import Path
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import wave
import numpy as np
from .model import ValidationError
from .runtime import ffmpeg_path, process_options

def ffmpeg():
    executable = ffmpeg_path()
    if not executable or not executable.is_file():
        raise ValidationError("FFmpeg is missing. Install it and restart the app, or set RSB_FFMPEG.")
    return str(executable)

def run(args, timeout=14400):
    try:
        return subprocess.run([ffmpeg(), "-nostdin", "-hide_banner", *map(str, args)],
                              capture_output=True, check=True, timeout=timeout, **process_options())
    except subprocess.CalledProcessError:
        raise ValidationError("FFmpeg could not process this audio. Check that the file is playable and the trim points are valid.") from None
    except subprocess.TimeoutExpired:
        raise ValidationError("Audio processing exceeded the time limit.") from None

def probe(path):
    try:
        result = subprocess.run([ffmpeg(), "-nostdin", "-hide_banner", "-protocol_whitelist", "file,pipe",
                                 "-i", str(path)], capture_output=True, timeout=30, **process_options())
    except subprocess.TimeoutExpired:
        raise ValidationError("Audio inspection timed out.") from None
    raw = result.stderr.decode(errors="replace")
    match = re.search(r"Duration: (\d+):(\d+):([\d.]+)", raw)
    if not match or "Audio:" not in raw:
        raise ValidationError("This file does not contain readable audio.")
    h, m, s = map(float, match.groups())
    seconds = h * 3600 + m * 60 + s
    if not .05 < seconds <= 14400:
        raise ValidationError("Audio duration must be between 0.05 seconds and four hours.")
    return seconds

def measure(path, target=-16, ceiling=-2, lra=11):
    result = run(["-i", path, "-af",
                  f"loudnorm=I={target}:TP={ceiling}:LRA={lra}:print_format=json", "-f", "null", "-"])
    log = result.stderr.decode(errors="replace")
    try:
        obj, _ = json.JSONDecoder().raw_decode(log[log.rfind("{"):])
        if not math.isfinite(float(obj["input_i"])):
            raise ValueError()
        return obj
    except (ValueError, KeyError):
        raise ValidationError("This file is silent or its loudness could not be measured.") from None

def normalise(directory, asset, entry, s):
    speech = entry["kind"] == "speech"
    target = s["speech_lufs"] if speech else s["music_lufs"]
    ceiling, lra = min(-2, s["true_peak_db"] - .5), 7 if speech else 11
    recipe = {"sha256": asset["sha256"], "start": entry.get("trim_start", 0),
              "end": entry.get("trim_end"), "target": target, "ceiling": ceiling,
              "rate": s["sample_rate"], "speech": speech, "revision": 1}
    key = hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()
    cache = directory / "cache"
    cache.mkdir(exist_ok=True)
    output = cache / (key + ".wav")
    if output.exists():
        return output
    raw = cache / (key + "-input.wav")
    args = ["-v", "error", "-y", "-protocol_whitelist", "file,pipe",
            "-ss", str(recipe["start"]), "-i", directory / "assets" / asset["file"]]
    if recipe["end"] is not None:
        args += ["-t", str(recipe["end"] - recipe["start"])]
    filters = "highpass=f=65,acompressor=threshold=0.125:ratio=2.5:attack=5:release=90:makeup=1" if speech else "anull"
    try:
        run(args + ["-map", "0:a:0", "-vn", "-map_metadata", "-1", "-af", filters,
                    "-ar", s["sample_rate"], "-ac", "2", "-c:a", "pcm_s16le", raw])
        stats = measure(raw, target, ceiling, lra)
        filt = (f"loudnorm=I={target}:TP={ceiling}:LRA={lra}:"
                f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
                f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
                f"offset={stats['target_offset']}:linear=true")
        temp = cache / (key + "-output.wav")
        run(["-v", "error", "-y", "-i", raw, "-af", filt, "-ar", s["sample_rate"],
             "-ac", "2", "-c:a", "pcm_s16le", temp])
        with wave.open(str(temp)) as w:
            if w.getnframes() < 2:
                raise ValidationError("The selected audio range is empty.")
        temp.replace(output)
        return output
    finally:
        raw.unlink(missing_ok=True)

def frames(path):
    with wave.open(str(path)) as w:
        return w.getnframes()

def overlap(previous, current, s, rate, lengths):
    if previous and previous["kind"] == current["kind"] == "music":
        return min(round(s["crossfade_seconds"] * rate), lengths[previous["id"]] // 4,
                   lengths[current["id"]] // 4)
    return 0

def timing(project, lengths, precise=False):
    s, seq = project["settings"], project["entries"]
    rate = s["sample_rate"] if precise else 1
    jingle = bool(project.get("jingle_id"))
    lead = round(s["intro_seconds"] * rate) if jingle else 0
    tail = round(s["outro_seconds"] * rate) if jingle else 0
    overlaps = [overlap(seq[i-1] if i else None, e, s, rate, lengths) for i, e in enumerate(seq)]
    base = sum(lengths.values()) - sum(overlaps) + lead + tail
    target = round(s["target_seconds"] * rate)
    extra = max(0, target - base) if s["duration_mode"] == "exact" else 0
    problems = []
    if s["duration_mode"] == "exact":
        if base > target:
            problems.append(f"The rundown is {(base-target)/rate:.2f} seconds too long. Remove a segment, choose trim points or use natural duration.")
        if extra and not jingle:
            problems.append("Exact duration needs a jingle to fill the remaining time, or more content.")
        if extra / rate > 120:
            problems.append(f"The rundown is {extra/rate:.1f} seconds short. Add content or use natural duration; automatic jingle padding is limited to two minutes.")
    return {"base_seconds": base/rate, "extra_jingle_seconds": extra/rate,
            "expected_seconds": (base + extra)/rate, "problems": problems,
            "lead_frames": lead, "tail_frames": tail + extra, "overlap_frames": overlaps}

def analyse(project):
    lengths, missing = {}, []
    for e in project["entries"]:
        asset = project["assets"].get(e.get("asset_id"))
        if not asset:
            missing.append(e["title"] or e["kind"])
            value = e["estimated_seconds"]
        else:
            end = e["trim_end"] if e["trim_end"] is not None else asset["duration_seconds"]
            if end > asset["duration_seconds"] + .1 or e["trim_start"] >= end:
                raise ValidationError("Trim points exceed the audio duration: " + e["title"])
            value = max(.01, end - e["trim_start"])
        lengths[e["id"]] = value
    # Durations from compressed file headers are estimates; the renderer uses decoded sample counts.
    s = project["settings"]
    base = sum(lengths.values())
    for a, b in zip(project["entries"], project["entries"][1:]):
        if a["kind"] == b["kind"] == "music":
            base -= min(s["crossfade_seconds"], lengths[a["id"]]/4, lengths[b["id"]]/4)
    if project.get("jingle_id"):
        base += s["intro_seconds"] + s["outro_seconds"]
    return {"base_seconds": base, "difference_seconds": base-s["target_seconds"],
            "missing": missing, "estimated": bool(missing), "segment_seconds": lengths,
            "note": "Final timing is calculated from decoded audio samples."}

class Bed:
    def __init__(self, path, rate):
        self.w = wave.open(str(path))
        self.length = self.w.getnframes()
        self.rate = rate

    def read(self, start, count):
        chunks = []
        while count:
            pos = start % self.length
            n = min(count, self.length-pos)
            self.w.setpos(pos)
            x = np.frombuffer(self.w.readframes(n), dtype="<i2").reshape(-1, 2).astype(np.float32)/32768
            # A short dip at the loop boundary avoids clicks on non-looping music.
            positions = np.arange(pos, pos+n)
            gain = np.minimum(np.minimum(positions, self.length-1-positions) / max(1, .012*self.rate), 1)
            x *= gain[:, None]
            chunks.append(x)
            start += n
            count -= n
        return np.concatenate(chunks) if len(chunks) > 1 else chunks[0]

    def close(self):
        self.w.close()

def edge_fade(x, start, total, rate, seconds=.008):
    pos = np.arange(start, start+len(x))
    gain = np.minimum(np.minimum(pos, total-1-pos)/max(1, seconds*rate), 1)
    return x * np.maximum(gain[:, None], 0)

def verify_mp3(path, expected_frames, rate, bitrate, ceiling):
    data = Path(path).read_bytes()
    pos = 10 + sum((data[6+n] & 127) << (7*(3-n)) for n in range(4)) if data[:3] == b"ID3" else 0
    rates = (44100, 48000, 32000)
    count, bitrates = 0, set()
    while pos + 4 <= len(data):
        h = int.from_bytes(data[pos:pos+4], "big")
        if h >> 21 != 0x7ff:
            if data[pos:pos+3] == b"TAG" or len(data)-pos < 128:
                break
            raise ValidationError("The MP3 contains an invalid frame.")
        if (h >> 19) & 3 != 3 or (h >> 17) & 3 != 1 or (h >> 10) & 3 == 3:
            raise ValidationError("Unexpected MP3 encoding.")
        br = (0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,0)[(h >> 12) & 15]
        hz = rates[(h >> 10) & 3]
        if hz != rate or br == 0:
            raise ValidationError("Unexpected MP3 sample rate or bitrate.")
        bitrates.add(br)
        pos += 144000 * br // hz + ((h >> 9) & 1)
        count += 1
    if bitrates != {bitrate}:
        raise ValidationError("The exported MP3 does not match the requested constant bitrate.")
    # Count actual decoded samples. Null-muxer progress timestamps vary between
    # FFmpeg releases and do not reliably describe gapless MP3 playback length.
    # A temporary stderr file also prevents a pipe deadlock on long ebur128 logs.
    byte_count = 0
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen([ffmpeg(), "-nostdin", "-hide_banner", "-i", str(path),
            "-af", "ebur128=peak=true", "-ar", str(rate), "-ac", "2", "-f", "f32le", "pipe:1"],
            stdout=subprocess.PIPE, stderr=log, **process_options())
        try:
            while True:
                block = process.stdout.read(1024*1024)
                if not block:
                    break
                byte_count += len(block)
            if process.wait(timeout=14400) != 0:
                raise ValidationError("The exported MP3 could not be decoded for verification.")
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
        log.seek(0, 2)
        log.seek(max(0, log.tell()-16000))
        summary = log.read().decode(errors="replace").rsplit("Summary:", 1)[-1]
    decoded_frames = byte_count // 8
    if byte_count % 8 or decoded_frames != expected_frames:
        raise ValidationError(f"Export duration mismatch: expected {expected_frames} samples, decoded {decoded_frames}.")
    try:
        i = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1))
        tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary).group(1))
        lra = float(re.search(r"LRA:\s+([\d.]+) LU", summary).group(1))
    except (AttributeError, ValueError):
        raise ValidationError("Could not verify export loudness.") from None
    return {"integrated_lufs": i, "true_peak_db": tp, "loudness_range_lu": lra,
            "duration_seconds": expected_frames/rate, "bitrate_kbps": bitrate,
            "sample_rate": rate, "channels": 2, "cbr_verified": True, "mpeg_frames": count,
            "decoded_frames": decoded_frames, "decoded_sample_count_verified": True,
            "within_peak_ceiling": tp <= ceiling + .1}

def render(project, directory, progress=lambda value, message: None):
    seq, s = project["entries"], project["settings"]
    if not seq:
        raise ValidationError("Add at least one segment.")
    info = analyse(project)
    if info["missing"]:
        raise ValidationError("Upload audio for: " + ", ".join(info["missing"]))
    rate = s["sample_rate"]
    prepared = {}
    for i, e in enumerate(seq):
        progress(.05 + .5*i/len(seq), "Preparing audio " + str(i+1) + " of " + str(len(seq)))
        prepared[e["id"]] = normalise(directory, project["assets"][e["asset_id"]], e, s)
    jingle = None
    if project.get("jingle_id"):
        progress(.56, "Preparing the jingle")
        jingle = normalise(directory, project["assets"][project["jingle_id"]],
                           {"kind": "music", "trim_start": 0, "trim_end": None}, s)
    lengths = {eid: frames(path) for eid, path in prepared.items()}
    plan = timing(project, lengths, precise=True)
    if plan["problems"]:
        raise ValidationError(" ".join(plan["problems"]))
    progress(.6, "Assembling the show")
    output_dir = directory / "exports"
    output_dir.mkdir(exist_ok=True)
    master = output_dir / "master.pcm"
    bed = Bed(jingle, rate) if jingle else None
    timeline, cursor = [], 0
    chunk = rate * 4
    total = sum(lengths.values()) - sum(plan["overlap_frames"]) + plan["lead_frames"] + plan["tail_frames"]
    lead, tail = plan["lead_frames"], plan["tail_frames"]
    try:
        with master.open("w+b") as out:
            def write(x):
                nonlocal cursor
                out.write(np.rint(np.clip(x, -1, 1)*32767).astype("<i2").tobytes())
                cursor += len(x)

            if lead:
                for pos in range(0, lead, chunk):
                    n = min(chunk, lead-pos)
                    x = bed.read(pos, n)
                    t = np.arange(pos, pos+n)/rate
                    gain = np.minimum(t/.02, 1)
                    if seq[0]["kind"] == "speech":
                        db = np.interp(t, [0, max(0, lead/rate-2), lead/rate], [0, 0, s["bed_db"]])
                        gain *= 10**(db/20)
                    else:
                        gain *= np.minimum((lead/rate-t)/min(2, lead/rate), 1)
                    write(x*gain[:, None])
                timeline.append({"kind": "jingle", "title": "Opening jingle", "start_seconds": 0, "duration_seconds": lead/rate})
            for i, e in enumerate(seq):
                overlap_n = plan["overlap_frames"][i]
                start = cursor-overlap_n
                length = lengths[e["id"]]
                timeline.append({"id": e["id"], "kind": e["kind"], "title": e["title"],
                                 "start_seconds": start/rate, "duration_seconds": length/rate,
                                 "crossfade_seconds": overlap_n/rate,
                                 "bed_db": s["bed_db"] if bed and e["kind"] == "speech" else None,
                                 "trim_start": e["trim_start"], "trim_end": e["trim_end"]})
                with wave.open(str(prepared[e["id"]])) as w:
                    pos = 0
                    if overlap_n:
                        raw = np.frombuffer(w.readframes(overlap_n), dtype="<i2").reshape(-1, 2).astype(np.float32)/32768
                        x = edge_fade(raw, 0, length, rate)
                        out.seek(-overlap_n*4, 1)
                        previous = np.frombuffer(out.read(overlap_n*4), dtype="<i2").reshape(-1, 2).astype(np.float32)/32768
                        ramp = np.linspace(0, 1, overlap_n)[:, None]
                        mixed = previous*(1-ramp) + x*ramp
                        out.seek(-overlap_n*4, 1)
                        cursor -= overlap_n
                        write(mixed)
                        pos = overlap_n
                    while pos < length:
                        n = min(chunk, length-pos)
                        x = np.frombuffer(w.readframes(n), dtype="<i2").reshape(-1, 2).astype(np.float32)/32768
                        x = edge_fade(x, pos, length, rate)
                        if bed and e["kind"] == "speech":
                            bg = bed.read(start+pos, n)
                            t = np.arange(pos, pos+n)
                            gain = np.minimum(np.minimum(t, length-1-t)/max(1, .25*rate), 1)
                            # Connect the opening and closing bed without a dip.
                            if i == 0 and lead:
                                gain[t < .25*rate] = 1
                            if i == len(seq)-1 and tail:
                                gain[t > length-.25*rate] = 1
                            x += bg * (10**(s["bed_db"]/20)*np.maximum(gain[:, None], 0))
                        write(x)
                        pos += n
            if tail:
                start = cursor
                for pos in range(0, tail, chunk):
                    n = min(chunk, tail-pos)
                    x = bed.read(start+pos, n)
                    t = np.arange(pos, pos+n)/rate
                    gain = np.minimum((tail/rate-t)/min(5, tail/rate), 1)
                    if seq[-1]["kind"] == "speech":
                        db = np.interp(t, [0, min(2, tail/rate)], [s["bed_db"], 0])
                        gain *= 10**(db/20)
                    write(x*gain[:, None])
                timeline.append({"kind": "jingle", "title": "Closing jingle", "start_seconds": start/rate, "duration_seconds": tail/rate})
        if cursor != total:
            raise RuntimeError("Assembly sample count mismatch.")
        progress(.75, "Measuring the complete mix")
        # Measure the raw master once, then apply only a global gain and an oversampled limiter.
        measured = run(["-f", "s16le", "-ar", rate, "-ac", "2", "-i", master,
                        "-af", "ebur128=peak=true", "-f", "null", "-"])
        summary = measured.stderr.decode(errors="replace").rsplit("Summary:", 1)[-1]
        loudness = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1))
        gain_db = s["music_lufs"]-loudness
        # alimiter operates at 192 kHz to leave room for intersample peaks and MP3 encoding.
        limit_db = s["true_peak_db"]-.5
        filt = (f"volume={gain_db}dB,aresample=192000,"
                f"alimiter=limit={10**(limit_db/20)}:level=false:latency=true,"
                f"aresample={rate}")
        output = output_dir / "show.mp3"
        temp = output_dir / "show-working.mp3"
        progress(.82, "Encoding the MP3")
        run(["-v", "error", "-y", "-f", "s16le", "-ar", rate, "-ac", "2", "-i", master,
             "-af", filt, "-map_metadata", "-1", "-c:a", "libmp3lame",
             "-b:a", str(s["bitrate_kbps"])+"k", "-ar", rate, "-ac", "2",
             "-metadata", "title="+project["title"], "-metadata", "album=Radio Show Builder", temp])
        progress(.94, "Verifying duration, bitrate and peak level")
        report = verify_mp3(temp, total, rate, s["bitrate_kbps"], s["true_peak_db"])
        if not report["within_peak_ceiling"]:
            # One conservative re-encode from the PCM master, never from a lossy intermediate.
            correction = s["true_peak_db"]-report["true_peak_db"]-.4
            run(["-v", "error", "-y", "-f", "s16le", "-ar", rate, "-ac", "2", "-i", master,
                 "-af", filt+f",volume={correction}dB", "-map_metadata", "-1", "-c:a", "libmp3lame",
                 "-b:a", str(s["bitrate_kbps"])+"k", "-ar", rate, "-ac", "2",
                 "-metadata", "title="+project["title"], "-metadata", "album=Radio Show Builder", temp])
            report = verify_mp3(temp, total, rate, s["bitrate_kbps"], s["true_peak_db"])
        if not report["within_peak_ceiling"]:
            raise ValidationError("The encoded peak level is above the requested ceiling. Choose a lower ceiling and render again.")
        temp.replace(output)
        report.update({"timeline": timeline, "settings": s, "master_gain_db": gain_db,
                       "music_tracks": sum(e["kind"] == "music" for e in seq),
                       "speech_segments": sum(e["kind"] == "speech" for e in seq),
                       "source_files_unchanged": True, "checks_passed": True})
        (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = [project["title"], f"{total/rate:.3f} seconds | {s['bitrate_kbps']} kbps CBR | {rate} Hz stereo", ""]
        for e in timeline:
            seconds = round(e["start_seconds"])
            lines.append(f"{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}  {e['kind'].upper()}  {e['title']}")
        (output_dir / "rundown.txt").write_text("\n".join(lines)+"\n", encoding="utf-8")
        progress(1, "Your show is ready")
        return report
    finally:
        if bed:
            bed.close()
        master.unlink(missing_ok=True)
