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

## Auto Clipper milestone
- AI Director CI 45922109564 completed successfully (mocked local AI contract; real Ollama inference still unverified).
- Added deterministic 15/30/60-second candidate ranking, overlap rejection, up to ten suggestions, source preview, individual and sequential batch MP4 exports, current caption/music settings and separate batch storage.
- Added ranking, validation and real render tests. New CI pending. No semantic video analysis, virality prediction or automatic publishing.

## Social exports and private Docker release candidate
- Clipper CI 45922285900 passed; PR #2 merged to main at 30252662ab7228f2e4dafbb0e4db9ebaef816e2f.
- Added allowlisted 720p/1080p aspect presets, fit and center crop, original mode, main and batch export integration, geometry tests.
- Added non-root private Docker image, loopback Compose binding, resource limits, health endpoint, container CI smoke test and VPS instructions. No live server deployment performed. CI pending.

## Saved projects milestone
- Social format/container CI 45922432058 was in progress when this increment began.
- Added validated versioned JSON project saves, source reopen, soundtrack snapshot isolation, explicit deletion, saved-project picker and optional persistent Docker volume. Default remains ephemeral. Added round-trip and validation tests; new CI pending.
- No durable render queue, multi-user ownership, storage-volume quota or autosave. Unsaved orphan folders need owner cleanup; browser preview uses a source blob, not ranged streaming.

- Social export and private Docker CI 45922432058 passed. Added saved-project HTTP round-trip test, explicit delete-only orphan entries, named deletion confirmation, and source MIME preservation independent of project name. Latest CI pending.

## Advanced rendering milestone
- Saved-project CI was in progress at start; previous social/container CI passed.
- Added single-worker bounded in-memory export queue, actual FFmpeg timestamp progress, cancellation and temporary-file cleanup, main UI polling, quality presets, QHD/4K geometry and duration limits, persisted quality selection.
- Added queue ordering/cancel, render execution and preset validation tests. New CI pending. Clipper still renders synchronously, queue not durable, no rendered preview or 4K benchmark yet.

- Saved-project CI 45922606787 passed. Added real HTTP submission/poll/download integration coverage, controlled cancellation test protecting previous export, and portable progress-file reading. Latest CI pending.

## Owner access milestone
- PR #3 merged to main at b888e7440fae543825c25a2576bb767746af29d4; CI 45922817169 succeeded.
- Added optional private owner authentication, protected static editor/session/media and mutation endpoints, same-origin mutation checks, constant-time credential comparisons, restrictive browser headers, owner Compose overlay and HTTP security tests. Health endpoint remains minimal and anonymous. Latest CI pending.
- This is not Studio SSO or multi-tenant isolation; no deployment, new hosting or modifications to takatak-v1.

## Local usage and entitlement foundation
- Owner security CI 45926153893 passed; PR #4 merged at 147d4752a8178df6f843b7d97f1207cc91e6657a.
- Added transactional SQLite render-attempt ledger, optional monthly cap, completed/cancelled/failed/interrupted accounting, main and clipper integration, owner usage display and tests. No external billing; accepted failed/cancelled attempts count toward resource cap only. Proposed Studio integration contract documented; no changes to takatak-v1. New CI pending.

- Added HTTP regression coverage for usage authorization, completed/cancelled accounting and 429 quota rejection before render. Clipper cleanup now executes before accounting finalization. CI pending.

## Private workspace isolation
- Usage CI 45930401547 passed; PR #5 merged at eefbb5f108b9fbbc0f34b822a805b0cf2019c22f.
- Added optional explicit workspace configuration, server-selected project/media namespace, per-workspace CSRF and SQLite usage, scoped render status/cancel and private Compose overlay. Added HTTP regression tests for cross-workspace access and configuration traversal. New CI pending.
- Default owner mode unchanged; no changes to takatak-v1, real Studio SSO, billing or public deployment. Shared process/volume remains a limitation.

## Studio creative pack interoperability
- Workspace CI 45933244482 passed; PR #6 merged at 5a4939941baae22824ddeb37a62d3f901adb2538.
- Read V1 main 09c6f21f42d0ee39385ec5e11c389fba6a191205 workspace permission gate and actual Studio production_request_pack v1 contract. Added local creative-only pack parsing, authenticated import endpoint, explicit attachment, saved manifest field and regression tests. No V1 writes or SSO claims. Latest CI pending.

- Added pack HTTP import/save/open regression to workspace isolation test, restored canonical Director prompt on reopen, and matched upstream empty character-profile semantics. Latest CI pending.

## Studio gateway verification precursor
- PR #7 pack CI 45933475479 still running at start. Kept work on same branch; no unverified merge.
- Added opt-in receiver verifier with signed client/profile/permission/entitlement claims, one-to-one trusted workspace map, exact request method/target, 30-second TTL, bounded replay cache, no Basic fallback in gateway mode and HTTP isolation tests. No live issuer, body signature, restart-durable replay or public exposure. Latest CI pending.

## Gateway protocol v2 hardening
- Prior gateway CI 45933600623 in progress at start. No unverified merge.
- Added mandatory signed body SHA-256, exact authenticated body staging before mutation, strict length/transfer checks, bounded staging slot, persistent transactional replay store and cross-instance/restart replay tests. Updated protocol audience to v2, no compatibility fallback. New CI pending; issuer and secure transport still absent.

## Studio issuer reference
- Gateway V2 CI 45933769011 passed; PR #7 merged at 19aea1fb590fd1d0f0cc04ffa57e89644685df3d.
- Inspected current V1 permission guard, tenant access and Studio flag; no dedicated C4PCUT entitlement found. Added server-only Node reference issuer with injected authoritative access/entitlement checks, explicit route allowlist, exact body snapshots and short-lived signatures. Added Node unit tests and Node-to-Python interoperability tests. Latest CI pending. No V1 writes, live issuer, relay, billing or deployment.

- Owner pricing direction: match CapCut. Recorded verified Canadian App Store monthly reference prices (CAD 0/13.49/27.99) in disabled catalog and pricing policy. Annual pricing and feature allowances remain unresolved. No billing activated. Issuer CI 45934058126 in progress before catalog commit.
