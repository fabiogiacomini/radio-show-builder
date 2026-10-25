# User guide

## Create your first podcast

1. Choose **Create a podcast** on the welcome screen, or choose **Podcast** in the sidebar's new-project preset and press **New podcast**.
2. Give the episode a title, describe its subject and audience, and choose the language and tone. The starting 30-minute duration is a script planning goal; the export keeps the natural length of your recordings.
3. Leave **Music in the draft** at **0%** for a spoken-only episode. Generate a draft using your selected AI, or choose **Write it myself** for opening, main story and closing sections. No API key is needed for the manual workflow.
4. Review the script and download the Word document for recording. You can also use recordings you already have and add or remove spoken segments to match them.
5. Upload a recording for each spoken segment. Leave **No jingle** selected to produce an episode with speech alone. Music, opening and closing themes, and speech beds are optional.
6. Open **Mix & export**, keep **Natural duration**, and build the MP3. Listen before publishing it through your own podcast host.

The app assembles existing recordings and exports an MP3. It does not record or synthesize voices, host podcasts, create RSS feeds, or publish to listening platforms.

## Choose a starting preset

**Podcast** starts at a 30-minute planning goal, 0% music in the draft, natural export duration and no music crossfade. **Radio show** starts at 90 minutes, 83% music in the draft, exact duration and three-second crossfades. Both use 192 kbps stereo at 48 kHz. These are editable starting settings, not restrictions.

Use the sidebar preset to create another project. It does not reset the current project. Existing projects retain their audio and mix settings when opened or updated. Music percentage is saved per project and only guides future script generation.

Examples: [spoken-only podcast](../examples/podcast-rundown.json) and [music-led radio show](../examples/starter-rundown.json).

## Plan and review

Create an episode or show, describe its subject and audience, and choose a language and tone. Add reliable research notes.

Generate a draft with your selected provider, or choose **Write it myself** for a manual starting rundown: three spoken sections for a podcast, or opening, music slot and closing for radio.

Edit titles, speech and notes in the rundown. Move entries or remove them. Review the editorial-checks section and verify factual claims and track versions.

A new generation replaces an existing draft only after confirmation. Existing uploads remain available.

Download the Word script for recording. Word edits are not automatically imported: copy revised passages back into the app. A portable rundown JSON can be exported and imported.

## Audio

Upload a file for each segment. Use its player to check the recording. The dropdown can reuse another file already uploaded to this project.

If you want a jingle, upload it once for opening, closing and speech beds. Choose **No jingle** for dry speech and no jingle sections.

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

Rundown JSON contains scripts and settings, without audio, assignments or credentials. Import it into a project and upload audio again.

To transfer a complete production, stop the app and copy its project directory from the data folder. Keep the backup private.

## Troubleshooting

- **FFmpeg missing:** portable packages include it; extract the entire package and keep supporting folders with the executable. For source installations, install FFmpeg, add it to PATH and restart. RSB_FFMPEG can specify its full executable path.
- **Launch URL required:** open the URL printed by the current app process. Each launch has a new private session.
- **Port occupied:** use --port 8766 or another available local port.
- **No model catalogue:** enter the model ID manually.
- **AI HTTP 401/403:** check the endpoint, key and permissions.
- **Incomplete draft:** increase output tokens, shorten the request or choose a suitable model.
- **Invalid rundown:** try a more capable text model or write the rundown manually.
- **Too short:** add content, lower the target or choose natural duration. Extra jingle padding is limited to two minutes.
- **Audio task failed:** check playback, trim points, FFmpeg and free disk space.

Provider error bodies and private filesystem paths are not exposed in UI errors.
