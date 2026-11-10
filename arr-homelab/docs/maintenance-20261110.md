# Arr container maintenance — 2026-11-10

The candidate preserves the live seven-service stack on ddocker, including Seerr,
the existing Gluetun network dependencies, all nine published ports, and the
`/mnt/Media` and `/mnt/Jestertek` mounts. The older Git snapshot omitted Seerr
and used retired Synology paths. The vars file must describe the verified paths.

Images are pinned to registry digests reviewed November 10. Targets are Sonarr
4.0.20.3014, Radarr 6.4.4.10685, Prowlarr 2.7.0.5723, qBittorrent 5.3.0,
FlareSolverr 3.5.2, and the newer Gluetun image. Seerr already matches the registry
and is pinned without a version upgrade. It must rejoin the new Gluetun namespace.

The live Compose rendering and candidate passed an exact comparison after removing
image references and equivalent null command/entrypoint fields. No mounts, ports,
environment values, dependencies or security options differ. VPN values stayed
inside the authenticated remote process. The existing `.env` supplies PIA_USER
and PIA_PASS; `/run/arr-stack.env` was absent at inspection. Do not create or commit
another credentials file. Keep the existing secret renderer and references.

Baseline API checks: 312 Sonarr series, 2,263 Radarr movies, 20 Prowlarr indexers.
Existing health findings include unavailable/removed indexer definitions, indexer
status, removed movies and collection-root issues. Those are separate configuration
findings, not proof of an image-update failure. Host-loopback access timed out;
the verified API access uses the host's 10.20.60.13 address and the configured ports.

Before rollout, finish Terminal's release installation on shared TrueNAS storage.
Verify the merged Git candidate, current backup and live preflight again. Pull the
pinned images before stopping applications; retain the old image IDs. Stop the
dependent apps before Gluetun, preserve application database recovery points, and
start Gluetun first. Require its VPN health before recreating every dependent app,
including unchanged Seerr. Verify versions, original library/indexer counts,
SQLite integrity, app endpoints, Seerr health, media mounts and the VPN route.

Install the desired Compose only after those gates pass. Preserve old images and
database recovery points until post-maintenance backups are verified. A schema
change can require restoring an app database before using its older image; merely
changing the image back is not a complete rollback. Do not prune images or volumes.

Status at preparation: candidate staged and preflight passed; no image pull,
container replacement, application/database backup or production cutover occurred.
