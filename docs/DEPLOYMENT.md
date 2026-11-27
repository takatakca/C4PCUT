# Private VPS release candidate
This is a single-user prototype, not a public SaaS. Do not attach a public Coolify domain or reverse proxy. No staging required; deploy only as a private owner-access container, isolated from existing TAKATAK apps. This package has no cloud billing integration.

## On the authorized VPS
Check available memory, disk and whether port 8765 is already occupied. Clone the repository (or use an existing clean checkout), checkout the verified release commit from main, and run:

    docker compose config
    docker compose up -d --build
    docker compose ps
    curl --fail http://127.0.0.1:8765/healthz

Connect from your workstation using an existing authorized SSH login:

    ssh -N -L 8765:127.0.0.1:8765 USER@YOUR_VPS

Open http://127.0.0.1:8765 locally. Import a short owned video, analyze it, export an original and a vertical clip, play both and verify dimensions/audio/captions. No passwords or keys in GitHub. The container is non-root, has a read-only root filesystem, a bounded temporary filesystem, and CPU/memory limits. Media and jobs are ephemeral and lost on restart; the 2 GiB temporary filesystem may fill on large batches. The standard image does not install Whisper or Ollama. Do not upload untrusted third-party media to this prototype.

## Rollback
Download required exports first. Run docker compose down to remove the service; no other application is changed.

## Before public SaaS
Require authentication and workspace ownership enforcement for every resource; media sandboxing and network egress controls, disk quotas, persistent storage, durable worker queue, cancellation and job limits, security/load review, TLS, account/billing integration and real model validation. Public deployment is not approved by this package.

## Optional persistent project storage
For a private owner-only deployment, use `docker compose -f compose.yaml -f compose.persist.yaml up -d --build`. This creates a named volume at /data. Explicit Save stores the edit manifest and soundtrack snapshot; sources and exports remain on disk until deletion. This volume is NOT size-limited by Compose; monitor available space, back it up and use a dedicated quota-limited filesystem before larger workloads. Do not run `down -v` unless deliberately deleting project data. Default Compose without the overlay remains ephemeral. No public access is supported.

## Render resource limits
The private main export queue runs one FFmpeg process at a time. Queue state is not restart-durable; cancel or finish exports before shutdown. QHD/4K presets are CPU intensive and limited to 120/60 seconds respectively. The default 2 CPU / 3 GiB container limit is deliberately conservative and may fail on demanding sources; verify available capacity before changing limits. No public worker isolation or quota accounting yet.

## Owner access protection
Use the owner overlay for an authenticated private instance, through an SSH tunnel only. From the authorized VPS shell, provision a unique random password of at least 24 characters without committing or pasting it into shared logs, export C4PCUT_OWNER_PASSWORD, then use `docker compose -f compose.yaml -f compose.persist.yaml -f compose.owner.yaml up -d --build`. Browser credentials: user `owner`, your provisioned password. The secret is available to the Docker administrator; use a trusted host and protect backups. Health checks remain anonymous but expose no project data. Local-only default configuration is unchanged. Basic authentication is not SSO, tenant isolation, a public TLS configuration, or billing; do not expose the port publicly. CSP prohibits framing the editor; future Studio integration must use a separate authorized navigation or a reviewed integration contract.

## Optional render-attempt quota
Set C4PCUT_MONTHLY_RENDER_SECONDS to an explicitly chosen nonnegative integer and add compose.quota.yaml to the private Compose command. The default is unlimited attempt seconds, not unlimited server capacity. The SQLite ledger follows /data when persistence is enabled. Run only one instance per storage root; interrupted attempts remain counted. No external billing or customer quotas are connected.

## Private workspace mode (optional)
Use a dedicated private persistent storage root and a trusted admin-provisioned JSON file (maximum eight workspace slugs). Each record contains password_sha256 (64 lowercase hex digits, SHA-256 of a unique random high-entropy password of at least 24 characters) and optional monthly_render_seconds (integer or null). Generate digests locally without putting passwords in Git or command history, e.g. python -c 'import getpass,hashlib; print(hashlib.sha256(getpass.getpass().encode()).hexdigest())'. Protect the config and ensure container UID 10001 can read it. Use separate browser profiles for different workspaces because HTTP Basic credentials are cached per origin. Export C4PCUT_WORKSPACES_FILE as the absolute config path, then use docker compose -f compose.yaml -f compose.workspaces.yaml up -d --build. Do not combine with owner or global quota overlays. Existing owner projects remain separate and are not migrated. Use a quota-limited filesystem for total storage and keep the service private via SSH tunnel. This is app-level namespace isolation, not separate OS sandboxes, public TLS or enterprise SSO. A compromised worker could still access the shared data volume. Restart to apply configuration changes.
