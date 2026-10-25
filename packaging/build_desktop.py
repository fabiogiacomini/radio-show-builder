"""Build a portable distribution on its native OS, with notices and manifest."""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import ssl
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from radio_show_builder import __version__


def build(target):
    os.environ["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "build/pyinstaller-cache")
    import PyInstaller.__main__
    expected = {"macOS-arm64": ("Darwin", {"arm64"}), "macOS-x64": ("Darwin", {"x86_64"}),
                "Windows-x64": ("Windows", {"AMD64", "x86_64"}), "Linux-x64": ("Linux", {"x86_64"})}
    system, machines = expected[target]
    if platform.system() != system or platform.machine() not in machines:
        raise RuntimeError("Build this target on its matching native operating system and architecture.")
    os.chdir(ROOT)
    notices = ROOT / "build" / "desktop-notices"
    notices.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "build/vendor/notices", notices / "audio-engine", dirs_exist_ok=True)
    versions = {}
    for name in ["numpy", "python-docx", "lxml", "typing_extensions", "certifi", "pyinstaller", "pyinstaller-hooks-contrib"]:
        dist = metadata.distribution(name)
        versions[name] = dist.version
        count = 0
        for file in dist.files or []:
            if not any(word in file.name.lower() for word in ["license", "copying", "notice"]):
                continue
            source = Path(dist.locate_file(file))
            if source.is_file():
                dest = notices / name / str(file).replace("..", "_")
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
                count += 1
        if not count:
            raise RuntimeError("Missing distribution license: " + name)
    openssl_version = ssl.OPENSSL_VERSION.split()[1]
    for name, url in [
        ("Python-LICENSE.txt", f"https://raw.githubusercontent.com/python/cpython/v{platform.python_version()}/LICENSE"),
        ("OpenSSL-LICENSE.txt", f"https://raw.githubusercontent.com/openssl/openssl/openssl-{openssl_version}/LICENSE.txt"),
    ]:
        with urllib.request.urlopen(url, timeout=60) as response:
            (notices / name).write_bytes(response.read())
    manifest = {"application": "Radio Show Builder", "creator": "Fabio Giacomini", "version": __version__,
                "target": target, "system": platform.system(), "machine": platform.machine(),
                "python": platform.python_version(), "openssl": ssl.OPENSSL_VERSION, "packages": versions,
                "audio_sources": json.loads((ROOT / "packaging/sources.json").read_text())}
    (notices / "build-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (notices / "README.txt").write_text(
        "Radio Show Builder was created by Fabio Giacomini. Its own code is MIT licensed.\n"
        "The separate FFmpeg executable is LGPL 2.1 or later and contains LAME (LGPL 2 or later).\n"
        "Exact corresponding audio-engine source archives are supplied in the same GitHub release,\n"
        "along with the build scripts in the tagged app source. No FFmpeg or LAME source changes are applied.\n"
        "https://github.com/fabiogiacomini/radio-show-builder/releases\n"
        "Other bundled components retain their own notices included in this folder.\n", encoding="utf-8")
    binary = ROOT / "build/vendor/bin" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    args = [str(ROOT / "packaging/entry.py"), "--name", "Radio Show Builder", "--onedir", "--noconfirm", "--clean", "--noupx",
            "--distpath", str(ROOT / "dist/desktop"), "--workpath", str(ROOT / "build/pyinstaller"),
            "--specpath", str(ROOT / "build"), "--paths", str(ROOT), "--collect-data", "radio_show_builder",
            "--collect-data", "docx", "--add-binary", f"{binary}:bin", "--add-data", f"{notices}:third-party",
            "--add-data", f"{ROOT / 'LICENSE'}:."]
    if sys.platform in ["darwin", "win32"]:
        args += ["--windowed"]
    if sys.platform == "darwin":
        args += ["--osx-bundle-identifier", "io.github.fabiogiacomini.radio-show-builder"]
    PyInstaller.__main__.run(args)
    if sys.platform == "darwin":
        content = ROOT / "dist/desktop/Radio Show Builder.app"
        executable = content / "Contents/MacOS/Radio Show Builder"
    else:
        content = ROOT / "dist/desktop/Radio Show Builder"
        executable = content / ("Radio Show Builder.exe" if sys.platform == "win32" else "Radio Show Builder")
    env = os.environ.copy()
    env.pop("RSB_FFMPEG", None)
    smoke = ROOT / "build" / f"smoke-{target}.json"
    subprocess.run([str(executable), "--self-test-report", str(smoke)], check=True, timeout=360, env=env)
    result = json.loads(smoke.read_text())
    if not result["ok"]:
        raise RuntimeError("Frozen executable failed the package diagnostics.")
    stage = ROOT / "build" / f"portable-{target}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copytree(content, stage / content.name, symlinks=True, dirs_exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", stage / "LICENSE.txt")
    shutil.copy2(ROOT / "docs/desktop-downloads.md", stage / "START-HERE.txt")
    shutil.copytree(notices, stage / "Third-party notices", dirs_exist_ok=True)
    output = ROOT / "dist/release"
    output.mkdir(parents=True, exist_ok=True)
    stem = f"Radio-Show-Builder-{__version__}-{target}"
    if sys.platform == "darwin":
        (stage / "Applications").symlink_to("/Applications", target_is_directory=True)
        archive = output / (stem + ".dmg")
        subprocess.run(["hdiutil", "create", "-volname", "Radio Show Builder", "-srcfolder", str(stage), "-ov", "-format", "UDZO", str(archive)], check=True)
    elif sys.platform == "win32":
        archive = Path(shutil.make_archive(str(output / stem), "zip", root_dir=stage))
    else:
        archive = Path(shutil.make_archive(str(output / stem), "gztar", root_dir=stage))
    shutil.copy2(smoke, output / smoke.name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / (archive.name + ".sha256")).write_text(digest + "  " + archive.name + "\n")
    print("Built and verified " + archive.name, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, choices=["macOS-arm64", "macOS-x64", "Windows-x64", "Linux-x64"])
    build(parser.parse_args().target)
