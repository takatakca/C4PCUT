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
