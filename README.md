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
