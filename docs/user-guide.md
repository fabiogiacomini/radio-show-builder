# User guide

## Plan and review

Create a show, describe its subject and audience, and choose a language and tone. Add reliable research notes.

Generate a draft with your selected provider, or choose **Write it myself** to create an opening, music slot and closing for manual editing.

Edit titles, speech and notes in the rundown. Move entries or remove them. Review the editorial-checks section and verify factual claims and track versions.

A new generation replaces an existing draft only after confirmation. Existing uploads remain available.

Download the Word script for recording. Word edits are not automatically imported: copy revised passages back into the app. A portable rundown JSON can be exported and imported.

## Audio

Upload a file for each segment. Use its player to check the recording. The dropdown can reuse another file already uploaded to this project.

Upload the jingle once for opening, closing and speech beds. Choose **No jingle** for dry speech and no jingle sections.

Replacing audio or removing a segment does not delete the original upload.

## Fit and mix

Check duration after assigning files. The preview uses header estimates; rendering uses decoded samples.

When the show is too long, consider removing a whole track and updating any spoken references. Optional start/end trims apply only to that segment. A blank end means the end of the file.

Select bitrate, sample rate, crossfades and jingle duration. More negative bed attenuation makes the background quieter.

Use exact duration for a fixed slot when content is already close to target; use natural duration to preserve the selected programme length.

Keep the app and computer running during a build. After completion, listen in the browser and download the MP3, rundown and report.

Saving production changes invalidates the old export link. Render the updated project again.

## Storage and transfer

Choose **Save changes** to save locally. Starting generation, upload or export also saves the form.

Rundown JSON contains scripts and settings, without audio, assignments or credentials. Import it into a show and upload audio again.

To transfer a complete production, stop the app and copy its project directory from the data folder. Keep the backup private.

## Troubleshooting

- **FFmpeg missing:** install it, add it to PATH and restart. RSB_FFMPEG can specify its full executable path.
- **Launch URL required:** open the URL printed by the current app process. Each launch has a new private session.
- **Port occupied:** use --port 8766 or another available local port.
- **No model catalogue:** enter the model ID manually.
- **AI HTTP 401/403:** check the endpoint, key and permissions.
- **Incomplete draft:** increase output tokens, shorten the request or choose a suitable model.
- **Invalid rundown:** try a more capable text model or write the rundown manually.
- **Too short:** add content, lower the target or choose natural duration. Extra jingle padding is limited to two minutes.
- **Audio task failed:** check playback, trim points, FFmpeg and free disk space.

Provider error bodies and private filesystem paths are not exposed in UI errors.
