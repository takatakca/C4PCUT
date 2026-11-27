# C4PCUT — TAKATAK AUTO CUT

Local-first automated video editing studio inspired by the supplied reference. The first release implements actual FFmpeg scene detection, selectable cuts, a preview and MP4 rendering. The Python-style script panel is a visualization of trusted operations, never arbitrary executable user code.

## Run locally
Requires Python 3.11+ and FFmpeg/ffprobe on PATH.
```sh
python3 server.py
```
Open http://127.0.0.1:8765. Import an MP4, MOV or WebM, analyze, click a segment to preview, toggle Keep to select clips, then export.

No paid services or API keys required. Temporary files are removed on normal shutdown. This is a single-user localhost prototype, not a public server. Do not expose it through Coolify until authentication, workspace isolation, rate limits, storage retention and worker quotas are implemented.

## Test
```sh
python3 -m unittest discover -s tests -v
```
FFmpeg integration tests are skipped when binaries are missing.

See [project status](docs/PROJECT_STATUS.md) and [worklog](WORKLOG.md).

Timeline enhancement: analysis also generates genuine scene thumbnails and source audio peak envelopes. Click the ruler to seek; undo/redo restores scene selection within the active session. Effects, captions and music tracks remain placeholders.

Click a scene to select it, edit its in/out times (seconds) and choose an effect, then Apply. Undo/redo covers selection and edits. The monitor shows source footage; the exported MP4 reflects trims and effects.

## Captions
Import an SRT file or optionally generate captions on the local CPU. Install optional dependencies with `python -m pip install -r requirements-ai.txt`, obtain a compatible local CTranslate2 Whisper model separately, and start with `C4PCUT_WHISPER_MODEL=/absolute/model/path python server.py`. No model downloads or hosted AI are triggered by the application. The source preview displays timed captions; export embeds a selectable MP4 subtitle track and offers a remapped SRT. Burned-in animated subtitles and word timing remain future work. Local transcription is optional and requires separate model testing.

## Music and beat cuts
Import an audio file up to 64 MB, or detect onsets from the original soundtrack. The local transient detector plots onset markers and an approximate BPM when enough intervals exist. Mix music with source audio using independent gain controls. Music is anchored to source time; selected cuts remove matching music intervals and short music is padded with silence. Beat-cut mode explicitly replaces scene cuts, trims and effects while keeping captions. Source monitor remains unmixed; export applies the mix. Music settings and replacing the segmentation are not part of undo history. No external services required.

## Cinematic presets
Choose Fade through black or Slow push-in in the scene effect selector. Auto cinematic applies a deterministic alternating set of zoom, warm, fade and contrast effects to selected scenes; existing trims are retained and undo restores edits. Zoom normalizes the sequence to 30 fps. Fades do not overlap, so subtitle/audio mapping remains unchanged. Preview still shows source footage, not rendered effects.

### Burned-in caption styles
Choose Classic, Bold or Karaoke before exporting. These styles are permanently rendered into the output pixels using FFmpeg/libass (requires FFmpeg with the ass filter and DejaVu Sans or a fallback font). SRT export remains available. Karaoke splits each cue's duration evenly across its words; it is not measured word-level speech alignment. Preview is an approximation. Selectable subtitles remain the default.

## AI Director
Analyze media, choose a preset (deterministic, ignores free-form prompt semantics) or Ollama, set a maximum duration, generate and review a plan, then explicitly apply it. Undo restores previous scene selection and edits. The optional AI mode requires Ollama already listening on 127.0.0.1:11434 with an installed model named in C4PCUT_OLLAMA_MODEL. It receives only bounded scene timestamps, caption excerpts and onset counts, not images or audio; no arbitrary code execution. Output is validated against source bounds, effect allowlist and duration. Actual model quality and availability require local testing. No cloud endpoint or model pull is triggered.

## Auto Clipper
Analyze footage, choose 15/30/60 seconds, up to ten suggestions and a fixed look. Candidate windows are ranked using available caption coverage, local audio onsets and scene boundaries; near-duplicate windows are rejected, so shorter media may return fewer clips. This is heuristic ranking, not a guarantee of virality or visual understanding. Preview seeks source footage. Render a candidate or render all sequentially; every MP4 uses current caption and music settings. Results are separate from the main edit. Generating another batch replaces previous batch files for that source; download any needed exports first. All files remain local and temporary. Social aspect ratios, persistent batch storage and model-ranked highlights remain planned.

## Social exports and private deployment
Choose original, vertical, square or landscape formats in 720p/1080p presets. Fit pads; crop centers the image (not AI subject tracking). Both main export and clipper use the selected format. Preview remains source footage. See [private Docker deployment guide](docs/DEPLOYMENT.md). No public deployment or persistent library is included.
