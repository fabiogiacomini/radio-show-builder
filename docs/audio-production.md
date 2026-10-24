# Audio production

Processing runs locally through FFmpeg. Original uploads remain unchanged.

## Defaults

| Setting | Default |
|---|---|
| Music target | -16 LUFS |
| Speech target | -17 LUFS |
| Final true-peak ceiling | -1.5 dBTP |
| Bed attenuation | -27 dB relative to the normalised jingle |
| Music crossfade | 3 seconds |
| Opening and minimum closing jingle | 12 seconds each |
| Export | 192 kbps CBR, 48 kHz stereo |

These are adjustable defaults. Set your station's required delivery specification.

## Processing order

1. Decode the selected range of each source.
2. Apply a 65 Hz high-pass filter and gentle compression to speech.
3. Measure and normalise each file in two passes.
4. Assemble using decoded frames at the selected sample rate.
5. Crossfade consecutive music tracks, capped at one quarter of either track's duration.
6. Add the jingle bed under speech and opening/closing sections with level ramps.
7. Measure the full mix and apply one global loudness adjustment.
8. Limit peaks at an oversampled rate, then encode directly from the PCM master.
9. Verify the encoded MP3. If needed, re-encode once from the PCM master with a conservative level correction.
10. Offer the export only after the checks pass.

Final loudness can differ from the source targets because of the global adjustment and limiter. The report contains measured final values.

## Timing

Natural duration preserves the selected content, including crossfade overlaps and jingles.

Exact duration rounds the target to the nearest output sample. The app can extend the closing jingle by at most 120 additional seconds. Otherwise the editor must adjust the rundown. It never silently cuts tracks or accelerates speech.

Trim points are seconds from the beginning of a file and apply only to that segment. Very short boundary fades prevent clicks. Jingle loops have short level dips and are not beat-matched.

## Space and limits

Uploads are limited to 512 MiB each. File duration and target duration are limited to four hours.

An hour of stereo 48 kHz 16-bit PCM is approximately 691 MB. Caches and exports need additional space. The assembly master is removed after a render, while normalised caches remain for reuse.

Stop the app before manually deleting a project's cache folder. The next render rebuilds it. Back up audio and project.json before deleting an entire production directory.

## Report

The JSON report records duration, bitrate, sample rate, channels, MPEG frame count, integrated loudness, loudness range, true peak, segment timings, trims, crossfades and speech-bed settings.

Technical checks do not replace listening. Review transitions, pronunciation, recording quality and musical balance before broadcast.
