import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import uuid
import wave
import numpy as np
from radio_show_builder import audio
from radio_show_builder.model import ValidationError, entries, new_project

def signal(path, duration, frequency, rate=48000):
    t=np.arange(round(duration*rate))/rate
    envelope=np.minimum(np.minimum(t/.02,(duration-t)/.02),1)
    mono=(.14*np.sin(2*np.pi*frequency*t)+.03*np.sin(2*np.pi*(frequency*1.51)*t))*envelope
    x=np.column_stack([mono,mono*.9])
    with wave.open(str(path),"wb") as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate)
        w.writeframes(np.rint(x*32767).astype("<i2").tobytes())

class AudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            audio.ffmpeg()
        except ValidationError:
            raise unittest.SkipTest("Install FFmpeg to run audio integration tests.")

    def project(self, root):
        p=new_project("A generated signal test")
        p["settings"].update(target_seconds=14,intro_seconds=1,outro_seconds=1,crossfade_seconds=.5)
        folder=Path(root);(folder/"assets").mkdir()
        ids=[]
        for n,(length,freq) in enumerate([(2,240),(3,400),(3,600),(2,280),(4,100)]):
            aid=uuid.uuid4().hex;filename=aid+".wav";path=folder/"assets"/filename
            signal(path,length,freq)
            p["assets"][aid]={"id":aid,"file":filename,"name":"Generated signal","duration_seconds":length,
                              "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"bytes":path.stat().st_size}
            ids.append(aid)
        p["entries"]=entries([{"kind":kind,"title":"Generated "+kind,"asset_id":aid}
                              for kind,aid in zip(["speech","music","music","speech"],ids)])
        p["jingle_id"]=ids[-1]
        return p

    def test_exact_render_has_real_cbr_peak_checks_and_preserved_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.project(tmp)
            hashes={a["file"]:a["sha256"] for a in p["assets"].values()}
            report=audio.render(p,Path(tmp))
            self.assertEqual(report["duration_seconds"],14)
            self.assertEqual(report["bitrate_kbps"],192)
            self.assertTrue(report["cbr_verified"])
            self.assertTrue(report["within_peak_ceiling"])
            self.assertEqual(report["music_tracks"],2)
            self.assertEqual(report["speech_segments"],2)
            voices=[e for e in report["timeline"] if e["kind"]=="speech"]
            self.assertTrue(all(e["bed_db"]==-27 for e in voices))
            self.assertEqual([e["crossfade_seconds"] for e in report["timeline"] if e["kind"]=="music"],[0,.5])
            self.assertFalse((Path(tmp)/"exports/master.pcm").exists())
            for file,digest in hashes.items():
                self.assertEqual(hashlib.sha256((Path(tmp)/"assets"/file).read_bytes()).hexdigest(),digest)
            decoded=audio.run(["-v","error","-i",Path(tmp)/"exports/show.mp3","-f","s16le","-ar","48000","-ac","2","pipe:1"])
            self.assertEqual(len(decoded.stdout)//4,14*48000)

    def test_natural_duration_at_44100_and_256kbps(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.project(tmp)
            p["settings"].update(duration_mode="natural",sample_rate=44100,bitrate_kbps=256)
            report=audio.render(p,Path(tmp))
            self.assertEqual(report["duration_seconds"],11.5)
            self.assertEqual(report["bitrate_kbps"],256)
            self.assertEqual(report["sample_rate"],44100)

    def test_overlong_exact_rundown_requires_editor_decision(self):
        p=new_project()
        p["settings"].update(target_seconds=10,intro_seconds=0,outro_seconds=0)
        p["entries"]=entries([{"kind":"music","title":"Long track"}])
        plan=audio.timing(p,{p["entries"][0]["id"]:20*48000},precise=True)
        self.assertTrue(any("too long" in x for x in plan["problems"]))

    def test_trim_outside_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.project(tmp)
            p["entries"][0]["trim_end"]=20
            with self.assertRaises(ValidationError):
                audio.analyse(p)
