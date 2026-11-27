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
