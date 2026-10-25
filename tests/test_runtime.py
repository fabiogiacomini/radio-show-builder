import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from radio_show_builder import audio, runtime
from radio_show_builder.model import ValidationError


class RuntimeTests(unittest.TestCase):
    def test_one_instance_per_data_directory_and_url_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            with runtime.Instance(tmp) as first:
                first.set_url("http://127.0.0.1:1234/#token=test")
                self.assertTrue(first.url_file.is_file())
                with self.assertRaises(runtime.AlreadyRunning):
                    with runtime.Instance(tmp):
                        pass
            self.assertFalse(first.url_file.exists())
            with runtime.Instance(tmp):
                pass

    def test_bundle_resolves_without_system_path_and_honours_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            name = "ffmpeg.exe" if runtime.sys.platform == "win32" else "ffmpeg"
            binary = Path(tmp) / "bin" / name
            binary.parent.mkdir()
            binary.touch()
            with patch.object(runtime.sys, "frozen", True, create=True), patch.object(runtime.sys, "_MEIPASS", tmp, create=True), patch.dict(os.environ, {}, clear=True), patch.object(runtime.shutil, "which", return_value=None):
                self.assertEqual(audio.ffmpeg(), str(binary))
                with patch.dict(os.environ, {"RSB_FFMPEG": str(Path(tmp) / "missing")}):
                    with self.assertRaises(ValidationError):
                        audio.ffmpeg()

    def test_frozen_linux_child_uses_original_library_path(self):
        with patch.object(runtime.sys, "frozen", True, create=True), patch.object(runtime.sys, "platform", "linux"), patch.dict(os.environ, {"LD_LIBRARY_PATH": "/bundle", "LD_LIBRARY_PATH_ORIG": "/system"}, clear=True):
            self.assertEqual(runtime.process_options()["env"]["LD_LIBRARY_PATH"], "/system")
            self.assertEqual(os.environ["LD_LIBRARY_PATH"], "/bundle")
