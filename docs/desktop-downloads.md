# Portable downloads

Radio Show Builder — The independent radio toolkit. Created by Fabio Giacomini.

Download the package for your computer from:
https://github.com/fabiogiacomini/radio-show-builder/releases/tag/v0.2.0

These are early portable builds. Python and the FFmpeg audio engine are included. No terminal setup, administrator access, subscription to the app or separate Python installation is required. A desktop browser is required. AI services may require their own account and API key; local models and manually written scripts remain supported.

## Choose a download

| Computer | File |
|---|---|
| Mac with Apple chip, macOS 15 or later | macOS-arm64.dmg |
| Mac with Intel processor, macOS 15 or later | macOS-x64.dmg |
| Windows 10/11, Intel or AMD 64-bit | Windows-x64.zip |
| Linux desktop, Intel or AMD 64-bit, glibc 2.35 or later (for example Ubuntu 22.04+) | Linux-x64.tar.gz |

These are separate architecture-specific builds, not universal binaries. Windows ARM, Linux ARM, Alpine Linux and older macOS versions are not validated by this release.

## macOS

Open the DMG and drag Radio Show Builder into Applications. Then open it from Applications. The app opens your browser at a private local address.

The app has an ad-hoc signature and is not Apple notarized. macOS may block first launch as an unverified developer. If this occurs, consult Apple's guidance at https://support.apple.com/102445 and verify the download source and checksum. Do not disable Gatekeeper or other system protections.

## Windows

Extract the entire ZIP into a folder you can write to. Open the Radio Show Builder folder, then double-click Radio Show Builder.exe. Keep its supporting folders alongside the executable. The app opens your default browser.

The executable has no paid publisher certificate. Windows may display an unknown-publisher or SmartScreen warning. Verify the release source and checksum before deciding whether to run it. No administrator rights are needed.

## Linux

Extract the TAR.GZ archive. Open the Radio Show Builder folder and run the Radio Show Builder executable. Some desktop file managers require choosing Run or allowing the executable to run. If necessary, start it from a terminal with:

~~~sh
./"Radio Show Builder"
~~~

The archive preserves executable permissions. This is a glibc desktop build, not an AppImage, DEB or RPM. A desktop browser must be available.

## Use, quit and update

The interface runs locally in your browser. Use **Quit app** in the top bar when finished; closing the browser tab alone does not stop the local server. Wait for any running render to finish before quitting. Changes in the current show are saved before quitting.

Shows are stored in the .radio-show-builder directory in your home folder, outside the application bundle. Keep a backup of this folder, including audio assets, before updating. Replacing the application does not remove show data. No programme audio, personal voice or API key is included in the downloads.

Reopening the app while it is running opens the same studio rather than another server. If a browser does not open automatically, open launch-url.txt inside the .radio-show-builder folder in your home directory and copy that address into your browser. This private session address is removed when the app exits; do not share it. The app uses an available local port in portable builds. It does not expose the server to the network.

## Verification and licenses

Each release includes SHA256SUMS and a smoke-test report for each platform. Checks cover opening the local interface, audio uploads, Word export, a complete 14-second generated-signal show at 192 kbps CBR, decoded duration, peak ceiling, original-file preservation and clean shutdown. They do not replace testing your own full-length show or all desktop environments.

Radio Show Builder's own code is MIT licensed, copyright 2026 Fabio Giacomini. Preserve the MIT notice when redistributing it. Bundled dependencies keep their separate licenses; see Third-party notices in the archive and application.

This distribution includes the separate FFmpeg executable, licensed under LGPL 2.1 or later, with LAME under LGPL 2 or later. Exact corresponding FFmpeg and LAME source archives are provided alongside the downloads in the same release. Build instructions and configuration are in packaging/build_ffmpeg.sh and the included audio-engine notices. FFmpeg: https://ffmpeg.org — license details: https://ffmpeg.org/legal.html
