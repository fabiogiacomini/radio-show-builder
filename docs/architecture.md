# Architecture

Dependencies are Python, NumPy, python-docx and external FFmpeg. The plain HTML/CSS/JavaScript frontend has no build step or remote assets.

| Module | Responsibility |
|---|---|
| model.py | Validation and project records |
| store.py | Atomic persistence and project locks |
| providers.py | Direct HTTP adapters and draft parsing |
| documents.py | Word export |
| audio.py | Normalisation, assembly, encoding and verification |
| server.py | Local HTTP server, uploads, jobs and downloads |
| static/ | Browser interface |

The threaded server is for one trusted local user. A two-worker executor handles long jobs. A running generation or render prevents changes to that project.

## Data

~~~text
data-directory/
  project-id/
    project.json
    script.docx
    assets/
      random-id.mp3
    cache/
      processing-recipe-hash.wav
    exports/
      show.mp3
      report.json
      rundown.txt
~~~

The default data folder is .radio-show-builder in the user's home. Use RSB_DATA_DIR or --data-dir to override it.

Audio uses random filenames. Original names stay in private project records. Cache keys include source hashes, trim points and processing settings.

## Access and credentials

The server binds to 127.0.0.1. A launch token becomes an HttpOnly, SameSite=Strict cookie; the token is removed from the address bar after exchange. Host and Origin checks restrict access to the local app.

Provider credentials stay in memory and go only to the chosen endpoint. Redirects are refused. FFmpeg network protocols are disabled for uploaded inputs.

This is not a public SaaS server.

## Extensions

Add a provider preset for an existing protocol, or an adapter for different APIs/authentication. Keep keys out of project records, disk writes and logs.

Keep audio timing explicit. Preserve uploads and verify the final lossy export. Do not silently shorten or speed up recordings.

## Current boundaries

- Jobs do not resume after restart, and this release has no cancellation control.
- No automatic web research, speech synthesis, music retrieval or beat matching.
- Word export is supported; edited Word import is not.
- Catalogue discovery does not guarantee model suitability.
- This app is intended for a trusted local user.
