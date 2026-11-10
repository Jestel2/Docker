# NMS Homelab

Docker-based monitoring stack for the home lab:

- LibreNMS with MariaDB, Redis, Dispatcher, and Oxidized integration.
- Oxidized network config backup with Git storage.
- Graylog standalone stack upgraded to 7.1.
- Akvorado 2.3 flow collector/search stack with Kafka, ClickHouse, Valkey, and Traefik.

This repo stores sanitized configuration and operating notes only. Runtime data, backups, database dumps, GeoIP databases, and secrets are intentionally excluded.

## Current Status

- LibreNMS desired state: pinned 26.10.2, with MariaDB 11.4.13 LTS in a separately restored database directory. November 10 live baseline was 26.6.1 / MariaDB 10.5.29; isolated restore and migration tests passed. Follow [the maintenance runbook](docs/maintenance-20261110.md) before the first rollout.
- LibreNMS Dispatcher: running with Redis cache.
- Oxidized: running after removing an unsupported HTTP hook.
- Graylog: upgraded from 5.x to 7.1; MongoDB is 7.0 with FCV 7.0.
- Akvorado: rebuilt and running on `http://10.20.60.15:8081`; listener ports are `2055/udp`, `4739/udp`, and `6343/udp`.

## Configuration Model

This stack is now managed as Git-backed desired state plus 1Password-backed secrets.

- Non-secret desired state lives in `vars/`.
- Secret references live in `.env.tpl` and other `.tpl` files.
- Real secret values live in 1Password.
- Runtime env files are rendered on the Docker host and should not be committed.

See `docs/config-model.md` and `docs/1password-secrets.md`.

## Deploying

Preferred flow:

1. Update Git-backed config or variables.
2. Update 1Password if a secret changes.
3. Run the matching `/secrets-test` command from Discord.
4. Run the matching `/redeploy` command from Discord.

Direct host fallback examples:

```bash
cd /opt/docker-stacks/nms-stack
sudo ./scripts/render-nms-secrets.sh
sudo docker compose --env-file /run/nms-stack.env up -d
sudo rm -f /run/nms-stack.env
```

```bash
cd /opt/graylog-stack
sudo ./scripts/render-graylog-secrets.sh
sudo docker compose --env-file /run/graylog-stack.env up -d
sudo rm -f /run/graylog-stack.env
```

```bash
cd /opt/docker/akvorado
sudo ./scripts/render-akvorado-secrets.sh
sudo docker compose --env-file /run/akvorado.env up -d
sudo rm -f /run/akvorado.env
```

## Repo Layout

- `stacks/nms-stack/`: LibreNMS, Redis, MariaDB, Oxidized, and disabled legacy embedded Graylog services.
- `stacks/nms-stack/oxidized/config.example`: redacted Oxidized config.
- `stacks/graylog-stack/`: standalone Graylog stack.
- `stacks/akvorado/`: Akvorado stack and config.
- `vars/`: non-secret desired state and 1Password references.
- `docs/`: review notes, upgrade notes, and work recommendations.
