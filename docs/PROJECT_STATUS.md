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

## Private access security
- Optional owner-only authentication and origin/CSRF checks, security headers, protected media/session endpoints and Compose overlay. Tests added, CI pending. Studio identity, entitlement verification, workspace ownership, public TLS, media worker sandboxing and durable quotas remain to be implemented. Default loopback-only usage remains supported.

## Usage foundation
- Private single-owner SQLite render-attempt ledger and optional UTC monthly seconds cap; tracks outcomes and persists with owner data. No monetary charges, per-tenant billing or live Studio SSO. Proposed trust boundary documented. New CI pending.

## Private workspace isolation
- Optional private multi-workspace namespaces with admin-provisioned credentials, distinct project stores, usage ledgers, CSRF tokens and scoped queue controls. Cross-workspace HTTP tests added; new CI pending. Shared worker/process and volume remain; actual TAKATAK identity/entitlements, storage quotas and public deployment not implemented.

## TAKATAK Studio pack interoperability
- Workspace isolation CI passed and PR #6 merged. Offline import of verified V1 production_request_pack v1 now implemented with creative-field whitelist, attachment to existing project, editable Director prompt and persisted brief. Identity and permissions remain from the authenticated C4PCUT workspace. Live SSO, product entitlements and payments remain pending. New CI pending.

## Studio gateway receiver
- Optional signed service request verification and workspace mapping implemented, disabled by default. Receiver tests added; new CI pending. No actual V1 issuer or product entitlement lookup, no live SSO, no public deployment. Private secure transport and replay durability remain prerequisites.

- Gateway v2 receiver now binds body bytes and persists nonce claims in SQLite; restart/cross-instance replay and tampering tests added. CI pending. Trusted issuer, verified entitlement lookup, worker sandboxing and live integration still not implemented.

## Studio issuer reference
- Gateway V2 CI passed and PR #7 merged. Server-only Node signing adapter implemented; requires real V1 guard and dedicated C4PCUT entitlement callback, explicit rollout flag and private key. Cross-language receiver tests added, new CI pending. Live V1 issuer and relay remain unconnected; dedicated grant, payments, worker isolation and deployment remain outstanding.

- Canadian monthly pricing catalog specified: Free CAD 0, Standard CAD 13.49, Pro CAD 27.99. Billing disabled; annual rates and plan allowances not yet verified or approved. No live payment or entitlement changes.

## Plan grant policy
- Validated disabled Canadian monthly catalog separately from authorization; explicit dedicated current plan grant required for reference issuer, including Free. Grant expiry caps assertion lifetime. Tests added, latest CI pending. No real V1 product entitlement store, payments, annual prices or per-plan allowances.

## Private grant registry reference
- PR #9 passed CI and merged. Optional operator-managed local access registry with explicit grants, revocation and audit; Node lookup rereads state. Tests added; CI pending. No real customers provisioned. Not authoritative V1 billing, live SSO or production deployment.

## V1 billing adapter candidate
- Read-only adapter matches observed GrowthSubscription schema with proposed dedicated C4PCUT keys, active period and client checks. Tests added; CI pending. No live lookup, SKU registration or payment verification. Actual V1 wiring, verified subscription lifecycle, plan allowances and deployment remain pending.

## Commercial catalog preflight
- PR #10 passed CI and merged. Draft disabled V1-compatible product/plan/price specification, read-only conflict preflight and tests implemented. Latest CI pending. No actual product registration or live billing; V1 integration and worker isolation remain open.

## Workspace capabilities
- Optional administrator-configured resource and feature restrictions enforced server-side; main/clipper render checks before accounting, original-resolution guard, session capability metadata. Tests added, CI pending. Commercial per-plan allocation and signed subscription-to-policy mapping not implemented. No real billing or deployment.

## Signed plan capability mapping
- PR #11 passed CI and merged. Gateway v3 signs plan, requires explicit capability profiles and applies intersection and effective monthly cap. New CI pending. No approved commercial quota values, actual V1 issuer or deployment.

## Editor account UI
- PR #12 CI passed and merged. Editor account and usage panel added with refresh and presentation-only gating. Server enforcement unchanged. Pure JS tests added; new CI pending, real browser smoke not yet verified. Live V1 and billing remain unconnected.

## Browser validation
- PR #13 passed original CI and merged. New real Chromium smoke workflow and editor quota/refresh fixes added. Exact browser CI result pending; no claim of browser pass or production deployment yet.

- Browser CI 45940304013: normal test job passed, browser dependency installation failed (nonexistent 1.51.1 pin). Updated to available 1.65.2 and explicit Ubuntu 24.04 runner. Browser workflow itself has not yet executed.

## Private admin reporting
- PR #14 passed both standard and real Chromium CI and merged. Private operator CLI read-only snapshot implemented; test suite pending. No live workspace report retrieved, no admin web UI or production billing connection.

## C4PCUT ADMIN V2
- PR #15 passed CI and merged. Private standalone HTML visual report added. Test suite pending. Read-only snapshot, not a live administrative web service; no V1 or production integration.

## Monitor effect preview
- PR #16 CI passed and merged. Standalone private admin visual report available. Optional browser source-time effect preview added; pure and Chromium tests pending. Not exact export preview or live deployment.

## Edited sequence monitor
- PR #17 passed CI and merged. Selected-trim playback, edited-time mapping, automatic gaps and stop/scrub controls implemented. New tests pending CI. Approximate source audio/visuals only, not exact FFmpeg playback, no live deployment.

## Audio monitor
- PR #18 passed CI and merged. Private normalized soundtrack playback, gain and source-time synchronization implemented; tests pending. Browser audio mix is approximate and dependent on browser autoplay/volume support. No new payment or production deployment.

- Audio CI 45944613873: standard tests pass, Chromium blocked by test-side unsafe-eval. Corrected locator assertions without relaxing CSP; hardened stale audio callbacks. Browser playback still pending exact-head validation.

## Timeline order and audio integration
- PR #19 merged after successful CI; independent Timeline PR #20 CI also green. Explicit scene ordering and project persistence integrated with source-time audio preview. Combined browser reorder test added. Latest combined CI required before main merge. Full overlapping multi-track editing, live TAKATAK integration, billing and worker isolation/deployment remain outstanding.

## Output title layer
- Combined timeline/audio PR #20 passed CI and merged. Independent output-time text titles implemented with bounded fixed-position styles and main MP4 burn-in, persisted projects and browser preview. CI pending; image/video overlays, live V1/billing, isolated deployment remain outstanding.

## Graphic title presets
- PR #21 passed CI and merged. Fixed banner styles and lower-third position implemented with saved-project compatibility and real render tests. New CI pending. Uploaded image and video overlays, live TAKATAK integration, billing and isolated production deployment remain outstanding.

- Graphic titles CI: Chromium passed; one FFmpeg frame-extraction test failed. Corrected seek timestamp; latest CI pending.

## PNG watermark
- Single bounded PNG logo, corner selection, normalized private asset, project persistence and MP4 composition implemented on stacked branch. New CI pending; parent graphic-title CI must pass first. General multi-layer image/video editing, production isolation and live integration remain open.

- Graphic titles merged after green CI; PNG watermark initial CI green. Retargeted PR #23 reconciled with main and enhanced timed watermark/size/opacity. Latest combined CI pending. General image/video tracks, actual commercial integration and production deployment remain outstanding.

## Picture-in-picture engine
- PR #23 passed CI and merged. Secondary-video normalization and composition engine added, tests pending. Not exposed in UI or HTTP; project persistence and workspace access still to implement. General multiple image/video layers, production integration and live deployment remain open.

## Picture-in-picture editor
- PR #24 engine CI passed and merged. Editor controls, authenticated asset upload/preview, saved project revision and main MP4 composition wired; tests pending. One silent secondary video per project, approximate preview. Multi-asset library and live TAKATAK integration/deployment remain outstanding.

## Sequence transitions
- PR #25 passed CI and merged. Independent duration-preserving dip transitions implemented, with persistent settings and approximate preview. Tests pending. General multi-asset timeline, true cross-dissolve, live V1 billing/integration and production isolation/deployment remain outstanding.

## Manual scene split
- PR #26 passed CI and merged. Manual source-playhead split implemented with preservation of selected duration and output order, project save and tests pending. Splits start a new undo history; transitions and per-scene effects may restart. Multi-asset timeline, live TAKATAK entitlement/billing and isolated production deployment remain outstanding.

## Scene topology undo/redo
- PR #27 passed CI and merged. Manual splits now retain session undo/redo history through authenticated server-side layout restoration; tests pending. History remains session-only. Multi-asset timeline, production integration and deployment still open.

## Adjacent scene joining
- PR #27 and #28 passed CI and merged. Topology undo/redo replaces previous split history reset. Adjacent join implemented with strict touching trims, matching effects and consecutive source/output order; new CI pending. Multi-asset timeline, live integration, billing and production deployment remain open.
