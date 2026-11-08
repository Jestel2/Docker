# JesterTek Docker stacks and automation

This repository contains homelab Compose stacks, configuration templates, and operational scripts. The former root-level **Hosted Apps Dashboard** has been retired from source on the cleanup branch. The root of this repository is **not** a deployable Docker Compose project.

## Retained components

- [ARR homelab](arr-homelab/README.md): Sonarr, Radarr, Prowlarr, qBittorrent and supporting configuration templates.
- [NMS homelab](nms-homelab/README.md): LibreNMS, Graylog, Akvorado, UniFi Network, Keep and related monitoring services.
- [Discord redeploy automation](automation/discord-redeploy-bot/README.md): script-based service checks and redeployment helpers.

Review the README and environment/secrets documentation **inside each stack** before deploying. Never add passwords, tokens, or live configuration secrets to Git.

## Cleanup note (November 7, 2026)

The old `hosted-apps` static dashboard (previously published from the repository-root Compose file on port 8088) is no longer part of the maintained source. This change does **not** stop or uninstall any already-running container, change a reverse proxy, remove persistent volumes, or alter any nested stacks. Verify runtime dependencies and stop the old `hosted-apps` service using the appropriate host-specific deployment procedure before merging a cleanup pull request.
