# Worklog
## 2026-11-26 — Foundation
- Initial local studio: reference-inspired dark layout, script panel, real progress log, preview and selectable video timeline.
- Python HTTP API and FFmpeg scene detection / selected-clip export.
- Unit and synthetic-media integration test definitions added.
- No production deployment or external AI enabled. CI/test execution not yet verified at authoring time.

## Timeline milestone
- Foundation CI run 45920730879 completed successfully before these changes.
- Added FFmpeg scene thumbnails, decoded audio peak envelopes, synchronized source-time playhead, ruler seeking and selection undo/redo.
- Added synthetic tone/thumbnail integration test. New commit verification pending.

## Scene editing milestone
- Added validated in/out edits, monochrome/warm/contrast render presets, effects lane and scene reset. Undo/redo now covers selection and scene edits.
- Source monitor does not yet preview rendered effects; output uses real FFmpeg filters. Added validation and rendered-pixel tests; CI pending.

## Caption milestone
- Scene editing CI 45921202768 and timeline CI 45921157245 passed.
- Added SRT validation, import, caption lane, source overlay, text editing, history, trim-aware subtitle remapping, MP4 selectable subtitles and SRT export.
- Added optional local Faster Whisper adapter; no automatic downloads or hosted AI. Model inference not tested by standard CI. New caption tests pending.

## Music milestone
- Caption CI 45921488435 was in progress at start of this increment.
- Added local bounded audio import, normalized WAV, source/music transient analysis, approximate tempo, waveform and markers, beat-derived replacement cuts, independent gains and FFmpeg mix with short-track padding.
- Added synthetic onset and mix tests. New CI pending. No claims of trained beat tracking or mixed live preview.

## Cinematic milestone
- Music CI 45921640888 and caption CI 45921488435 passed.
- Added duration-preserving fade through black, centered animated push-in, and deterministic batch cinematic styling with undo. Added real FFmpeg render test for duration, geometry and fade pixels.
- New CI pending; no overlap transitions or model-based style decisions yet.

## Burned-in captions milestone
- Cinematic CI 45921757518 passed.
- Added fixed classic/bold/karaoke ASS styles, validated mode selection, source preview styling and post-concat burn-in with output-time cues; SRT export preserved.
- Karaoke timing is estimated uniformly from cue duration, not speech alignment. Added ASS injection and rendered-pixel tests; current CI pending.

## Burn-in CI correction
- CI 45921934787 failed only at the raw grayscale frame extraction command in the burn-in test (render completed). Changed seek to canonical 0.7 and limited output encoder threads; now reports FFmpeg stderr on failure. Reverification pending.

## AI Director milestone
- Added bounded local preset planner and optional loopback-only Ollama JSON planner, scene/caption/onset summaries, strict selection/trim/effect/duration validation, review/apply interface and undo.
- Added deterministic and mocked Ollama contract tests; live model inference not verified. Presets do not interpret natural language. No semantic visual analysis yet.
