# Project status
## First milestone
- Local video import, scene boundary detection, event-driven visual editing, selected clip export.
- Five-track interface: video and source audio populated; effects, captions and music explicitly reserved.
- No claims of AI-generated edits, waveform analysis, captions, music sync or frame-accurate seeking in this milestone.

## Next milestones
1. Frame thumbnails, audio waveforms and true multitrack editing.
2. Whisper word timing, captions and non-destructive edit history.
3. Beat detection and music-video presets; 10 short clip suggestions.
4. Validated structured AI edit plans and optional local Ollama.
5. Authenticated TAKATAK Studio integration, persistent projects, isolated queue/render workers, resource quotas.
6. Deployment readiness, security and load tests, then approved production rollout.

## Timeline enhancement
- Implemented actual scene midpoint thumbnails and per-segment source audio peak envelopes, source-time playhead and selection undo/redo.
- Not yet verified by CI for this increment. True independent multitrack editing, trim handles and persistent history remain planned.

## Scene editing
- Per-scene non-destructive trim and three fixed render presets implemented with server validation; effects track shows chosen presets. Source monitor remains unprocessed. No arbitrary filter injection, independent layers, animated effects or live rendered preview yet. CI pending.

## Captions
- Source-time SRT import and text editing, timeline lane and preview overlay; output-time remapping across selected trims, selectable MP4 subtitle track and SRT export.
- Optional CPU Faster Whisper adapter requires installed dependency and a separately provisioned local model. Actual model inference not yet verified. Word-level timing, animated burn-in and caption timing editing remain planned. Caption CI pending.

## Music and beat cuts
- Local source/imported audio transient analysis and approximate tempo; music lane waveform and onset markers, explicit beat-cut segmentation and source-aligned gain-controlled render mixing.
- Heuristic onset detection (not a learned musical beat tracker). Source monitor does not play mixed music; music edits and resegmentation are not undoable. Cinematic transitions, beat-aware clip ranking and animated captions remain planned. Tests pending.

## Cinematic effects
- Added fade through black, slow animated centered zoom and deterministic batch cinematic styling. Zoom sequences normalize to 30 fps; fade preserves duration. Source monitor still shows unprocessed video. Overlapping crossfades, animated captions, rendered preview and model-directed effects remain planned. CI pending.

## Burned-in captions
- Classic, bold and estimated karaoke export styles implemented via FFmpeg/libass; browser preview approximates the style, SRT sidecar remains available. Exact word timestamps from a speech model, animated per-word transforms, and rendered preview remain planned. New CI pending.

- Burn-in CI 45921934787: 14 tests passed, one frame-extraction error. Test command adjusted; rerun required.

## AI Director
- Implemented preset and opt-in local Ollama edit planning with validated JSON, timeline application after review, and undo. Supports one chronological edit sequence from existing scenes; no multi-clip batch generation yet. Ollama receives metadata only, not imagery; live inference and new CI pending.

## Auto Clipper
- Implemented up to ten heuristic source-window suggestions, 15/30/60-second target, three fixed styles, individual and sequential batch export using current caption and music settings without replacing main timeline.
- Candidate ranking uses source scene boundaries, caption coverage and audio onsets; fewer clips are returned when windows would overlap excessively. Temporary batch files replaced by new suggestions. Model-based visual ranking, output aspect presets, durable queues and batch persistence remain planned. CI pending.

## Social formats / private release candidate
- Implemented 9:16, 1:1, 16:9 at 720/1080 widths or heights, original dimensions, fit and center crop; not subject tracking. Docker private deployment package and health checks added. CI pending. Persistent media, real AI model verification, SaaS authentication, durable workers, billing and public deployment remain open.

## Saved projects
- Explicit save/open/delete and versioned validated edit manifests, source media and immutable saved soundtrack snapshots, timeline regeneration. Persistent directory/Compose volume opt-in; default remains temporary. Eight folder cap. No persistent undo history, autosave, batch restoration, storage quota or public access; new CI pending.

- Previous social export/container CI passed. Saved project API lifecycle and orphan cleanup controls added; new checks pending.

## Advanced rendering
- Main export now uses bounded in-memory background queue with measured FFmpeg output-time progress and cancellation; global mutation gate protects source state. Optional QHD/4K portrait/landscape and three CRF profiles. New CI pending. Not durable, no full live preview, high-resolution performance unverified; batch clipper remains synchronous.

- Saved project CI passed. Rendering HTTP integration and cancellation cleanup tests added; no claim of successful latest CI yet.
