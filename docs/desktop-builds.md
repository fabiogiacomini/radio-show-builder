# Building portable packages

Build on the target operating system. PyInstaller is not a cross-compiler. The Desktop packages workflow uses standard GitHub-hosted runners: macos-15 (Apple Silicon), macos-15-intel, windows-2022 and ubuntu-22.04 (x64). Start the workflow manually on the revision intended for release. It uploads artifacts only; publishing a GitHub release remains a separate reviewed step.

## Build

Use Python 3.12, a C compiler, make and tar. Windows uses MSYS2 MINGW64 with GCC; other systems use their native compiler. Install the packaging dependencies in an isolated environment:

~~~sh
python -m pip install -r packaging/requirements.txt
python -m pip install --no-deps .
python packaging/fetch_sources.py
bash packaging/build_ffmpeg.sh
python packaging/build_desktop.py --target Linux-x64
~~~

Choose macOS-arm64, macOS-x64 or Windows-x64 as appropriate. On Windows, run the audio-engine build in an MSYS2 MINGW64 shell and the Python steps with native Windows Python, as shown in the workflow. Do not use MSYS Python to freeze the application.

The audio engine contains only the supported audio input formats, the libmp3lame encoder and the filters required by this app. It is compiled without GPL, nonfree or version3 options, without network protocols and without automatic external dependency discovery. FFmpeg and LAME are separate executables/libraries built from the unmodified source archives pinned in packaging/sources.json. LAME is statically linked into the separate FFmpeg executable; the MIT Python app communicates with FFmpeg using subprocesses, not library linking. The app accepts a user-supplied replacement through RSB_FFMPEG.

Release packages include the interpreter, Python dependencies, HTML/CSS/JavaScript, FFmpeg, creator copyright and third-party notices. Build output is under dist/release. The manifest records resolved dependency and Python versions and the exact audio-source hashes. No API keys, project folders or private audio are collected by the build.

## Checks and publication

Each platform runs the source test suite against its newly compiled FFmpeg and runs diagnostics inside the frozen executable. The offline diagnostics exercise local HTTP authentication, static resources, generated-audio upload, Word export and a complete 192 kbps MP3 render. Duration, decoded sample count, peak ceiling, original preservation and shutdown are checked. No paid model calls are made.

Before publication, verify all four builds succeed, inspect their reports, check the archive contents, and smoke-test the Mac app in a browser. Publish the four packages, their reports, SHA256SUMS and both exact audio source archives together in one release. Include a link to the LGPL notices and sources in the release description. Keep all corresponding sources downloadable for every released binary. Checksums identify downloaded artifacts; they are not a publisher signature.

The macOS package uses PyInstaller's ad-hoc signing and a DMG; Apple Developer ID signing/notarization is not configured. Windows uses an unsigned portable ZIP, and Linux uses a TAR.GZ preserving executable permissions. Certificates and signing services are optional future work requiring the maintainer's accounts and credentials. Do not disable system protections to work around unsigned builds.

Automated checks run on the named hosted systems. Compatibility with other OS releases or desktop/browser configurations is not implied. Source installations remain available separately.

## Primary references

- PyInstaller packaging model: https://pyinstaller.org/en/stable/operating-mode.html
- PyInstaller runtime paths and subprocess environment: https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html
- FFmpeg redistribution and source requirements: https://ffmpeg.org/legal.html
- GitHub runner platforms: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
