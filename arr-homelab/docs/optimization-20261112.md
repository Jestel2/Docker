# ARR optimization rollout — 2026-11-12

## Seerr security patch

Pin Seerr 3.5.2 to `sha256:aadee014b40e28cf9aa4928bc9d1183a6eb08f8c44d543cddc9efdcb16549be2`. [Upstream release](https://github.com/seerr-team/seerr/releases/tag/v3.5.2).

Deployment on ddocker (`10.20.60.13`) uses `/opt/docker-stacks/arr-stack/compose.yaml`. Pull before restarting. Stop only Seerr, retain a root-only backup of its configuration/database, deploy the merged Compose file with `docker compose up -d --no-deps seerr`, then verify the public settings endpoint, health, version and Arr integrations. Configuration backups contain credentials and must remain on the host outside Git. Retain the previous image/configuration for rollback; do not prune volumes or images.

The subsequent optimization rollout separates management networking, configures conservative Cleanuparr and Recyclarr policies, and validates VPN port forwarding. Existing media migration is a separate controlled task; both Seerr defaults already use TrueNAS.
