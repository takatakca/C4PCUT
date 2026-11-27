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

## Saved projects
Save explicitly to preserve source media, validated scene edits, captions, export settings and a soundtrack snapshot. Open restores the saved edit and regenerates timeline visuals. Undo history and clipper batches are not restored. Default storage remains temporary; set C4PCUT_DATA_DIR to an owner-only persistent directory or use the Compose persistence overlay. Delete permanently removes the selected project and media after confirmation. Maximum eight imported project folders per storage root; abandoned unsaved imports may require owner cleanup. Use browser-supported MP4 footage for reliable reopen playback. See deployment guide for disk precautions.

The project picker also lists unsaved/unreadable imported folders as delete-only entries; it never opens them as saved edits. Source MIME is saved separately from the editable project name.

## Rendering queue and quality
Main export submits a bounded in-memory queue (one worker, maximum three active jobs, one per project). The interface polls measured FFmpeg output time and offers cancellation. All other media mutations are blocked while the queue is active to keep source/soundtrack stable. Completed export URLs refer to the latest project export. Queue records are lost on restart; clipper rendering remains synchronous. QHD/4K portrait and landscape presets are available with fixed compact/standard/high CRF profiles. Explicit QHD renders are limited to 120 seconds and 4K to 60 seconds; upscaling cannot recover missing source detail. High-resolution real-world performance is not yet benchmarked. Progress is estimated from encoded timestamps, and a cancellation arriving after publication may complete normally.

## Private owner access
Optional C4PCUT_OWNER_PASSWORD enables Basic authentication for the entire editor and media API (except minimal health check). Use a unique long password and a trusted local/SSH-tunnel connection. The owner Compose overlay requires a configured password. Cross-origin mutation requests and missing CSRF tokens are rejected. This is a single-owner access boundary, not TAKATAK account integration or a public multi-tenant service.

## Local render usage
The owner-local SQLite ledger records rounded requested output seconds for main and clipper render attempts, with terminal outcomes. Optional C4PCUT_MONTHLY_RENDER_SECONDS sets a UTC calendar-month cap; unset means no cap. Cancelled, failed and interrupted accepted attempts still count toward this resource protection cap; queue rejections are excluded. This is not billable usage, no payments or customer subscriptions are enabled. Persistent storage retains the ledger across restarts. See docs/STUDIO_INTEGRATION.md for the proposed future account boundary.

## Private workspace mode
Optional administrator-provisioned workspace configuration gives each workspace separate project directories, in-memory job maps, CSRF tokens, and SQLite usage ledgers. Render status and cancellation are workspace-scoped; one shared worker and mutation lock protect host capacity. Credentials are workspace slug + unique high-entropy password over the private SSH tunnel. This is not public multi-tenant hosting or live TAKATAK login. The default single-owner mode is unchanged. See docs/DEPLOYMENT.md for setup and limits.

## Import a TAKATAK Studio creative brief
With footage imported, attach a TAKATAKSTUDIO production_request_pack v1 JSON (maximum 16 KiB). Review the populated project name and Director prompt; explicitly save to keep the whitelisted creative brief with the project. No jobs, identities, billing permissions, remote URLs or publishing instructions are imported. No AI runs until explicitly requested. This is offline interoperability, not SSO.

Optional private gateway assertion verifier has been implemented for future Studio service-to-service integration. It is disabled by default, requires a server-side workspace mapping and private signing key, verifies short-lived request-bound claims, and rejects replay within one running process. No V1 issuer or public SSO is connected. See docs/STUDIO_INTEGRATION.md.

Gateway receiver v2 adds mandatory exact body digest, bounded authenticated body staging and persistent SQLite nonce reservations. V1 assertions are rejected. See the v2 contract in docs/STUDIO_INTEGRATION.md.

Server-only Node issuer reference: integration/studio-issuer.mjs verifies injected authoritative workspace permission and dedicated C4PCUT entitlement before signing exact request bytes. It is not wired into TAKATAK v1; disabled by default and cannot be used as a browser token endpoint. Cross-language tests cover its compatibility with the Python receiver.

The reference issuer validates an explicit, current C4PCUT product grant for every plan, including Free. A disabled Canadian price catalog is validated separately; no plan selection can grant access or initiate payment. Plan quotas remain undecided.

Private grant registry reference: see docs/PRIVATE_GRANTS.md for offline explicit provisioning and revocation, audit history and read-only Node lookup. No actual clients were provisioned and no invoices are generated.

A read-only V1 GrowthSubscription adapter candidate is available in integration/v1-billing-adapter.mjs with explicit rollout flag and dedicated proposed plan keys. It is not connected to live V1 or Stripe; mocked integration tests exercise the contract.

Commercial catalog preflight candidate checks the proposed disabled C4PCUT product against V1 ProductCatalog shape, without mutation. See docs/V1_CATALOG_HANDOFF.md.

Optional private workspace capability profiles constrain export size/quality/duration, projects and selected AI/media features, before render quota reservation. No commercial plan allowances are assigned yet; see docs/DEPLOYMENT.md.

Gateway protocol v3 binds the validated plan to explicit server-managed profiles and intersects with workspace restrictions. Shared monthly ledger prevents quota reset on plan change. No commercial allowance defaults or live V1 wiring.

Editor account panel shows the authenticated plan or local/private mode, configured capability limits, monthly render-attempt usage, and disabled unavailable controls. Refresh manually or every 30 seconds while visible/idle. Server remains authoritative; no checkout or subscription management is simulated.

Chromium smoke in CI exercises the real private editor with generated two-second footage: restricted workspace, import/analyze/render/download, quota exhaustion and saved project lifecycle. No customer media or provider calls. Editor now disables export when known remaining quota is insufficient and serializes mutations during account refresh.

Private operator reporting: `python admin_report.py` reads configured workspaces, plan profiles, grant state and monthly ledger usage without initializing or changing ledgers. No HTTP administration route or live billing integration; see docs/PRIVATE_GRANTS.md.

C4PCUT ADMIN V2: append `--html /private/new-report.html` to the private admin report command to create a standalone visual dashboard. Status groups, usage meters, effective capabilities and summary metrics are available offline; no external scripts, HTTP admin endpoint, billing controls or live data connection. New files only, mode 0600.

Optional monitor effect preview applies approximate browser filters for committed scene edits (mono, warm, contrast, fade, zoom) at source time. Trimmed/excluded portions show original footage. Toggle off for unmodified source view. It is not an exact FFmpeg/output framing, cut-sequence or music preview.

Play edited sequence previews selected trims in source order, jumps across excluded ranges, and exposes a separate edited-time scrubber. Playback is approximate (browser seek/frame timing), source audio only; no soundtrack mix or export geometry preview. No rendering quota is consumed by playback.

Edited sequence audio monitor uses the normalized private WAV soundtrack and source-time cut alignment, approximate drift correction and volume controls. It pauses music on seeks/stalls/stop and restores ordinary source volume. Browser mixing is not FFmpeg limiter-accurate; mobile autoplay/volume behavior may vary. No render quota for preview.

Timeline output-order strip supports drag-and-drop and earlier/later buttons. Explicit selected-scene permutation drives playback and FFmpeg export; saved projects preserve order, old projects default to chronological. Source tracks remain chronological; captions and music follow source intervals into output order. No arbitrary overlapping multi-layer editing yet.

Output title track: up to 12 non-overlapping plain-text titles, top/center, anchored to edited output time, persisted with projects and burned into main MP4 alongside optional captions. Sequence playback provides approximate preview. Titles extending past shortened output are clipped or hidden. Auto Clipper remains independent; arbitrary video/image layers are not yet implemented.

Graphic title presets: classic, purple banner and dark banner; top, center or lower-left third above normal caption area. Fixed colors and styles only; existing projects default to classic. Monitor styling is approximate; MP4 composition uses libass.

Single PNG watermark: 2 MiB upload, maximum 1024×1024, fixed corner and size, normalized into private RGBA PNG. Saved project revisions retain the asset independently. Main MP4 only; no general image/video layering. Browser preview is approximate.
