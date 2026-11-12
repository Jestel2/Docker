# ARR Homelab Stack

Current networking, maintenance policy, verification and secure activation requirements: [November 12 optimization runbook](docs/optimization-20261112.md).

Docker Compose backup for the ARR/qBittorrent/Gluetun stack on `10.20.60.13`.

This repository folder stores sanitized stack configuration and lightweight app examples. Runtime databases, logs, downloads, app backup folders, API keys, WebUI password hashes, and VPN credentials are intentionally excluded.

## Services

- Gluetun with Private Internet Access over OpenVPN.
- qBittorrent behind Gluetun network namespace.
- Sonarr behind Gluetun.
- Radarr behind Gluetun.
- Prowlarr behind Gluetun.
- FlareSolverr behind Gluetun.
- Seerr behind Gluetun.

## Current Layout

```text
/opt/docker-stacks/arr-stack
```

The active `/opt/docker-stacks/arr-stack/compose.yaml` publishes application ports from the Gluetun container because the other services use `network_mode: "service:gluetun"`.

## Published Ports

- `8080/tcp`: qBittorrent WebUI
- `8989/tcp`: Sonarr
- `7878/tcp`: Radarr
- `9696/tcp`: Prowlarr
- `8191/tcp`: FlareSolverr
- `5055/tcp`: Seerr
- Additional live mappings preserved: `9898`, `7879`, `9697` (purpose unverified).

## Configuration Model

This stack is now managed as Git-backed desired state plus 1Password-backed secrets.

- Non-secret variables live in `vars/arr.yml`.
- Secret references live in `.env.tpl`.
- Real secret values live in the `ARR Stack` item in 1Password.
- The runtime env file is rendered on the Docker host and should not be committed.

See `docs/config-model.md` and `docs/1password-secrets.md`.

## Deploying

Preferred flow:

1. Update Git-backed config or variables.
2. Update 1Password if a secret changes.
3. Run `/secrets-test target:arr` from Discord.
4. Run `/redeploy target:arr` from Discord.

Direct host fallback:

```bash
cd /opt/docker-stacks/arr-stack
sudo ./scripts/render-arr-env.sh
sudo docker compose --env-file /run/arr-stack.env up -d
sudo rm -f /run/arr-stack.env
```

Do not commit real VPN credentials or app API keys.

## November 10 maintenance

The verified live topology and reviewed image digests are in Git. Preparation does not establish production rollout; see [the maintenance runbook](docs/maintenance-20261110.md) for versions, baseline counts, checks and recovery requirements.
