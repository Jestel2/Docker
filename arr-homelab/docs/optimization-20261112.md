# ARR optimization rollout — 2026-11-12

## Desired state and rollout

Host: ddocker (`tberno@10.20.60.13`). Runtime: `/opt/docker-stacks/arr-stack/compose.yaml`. Canonical repository: [Jestel2/Docker](https://github.com/Jestel2/Docker), `arr-homelab/`.

The Seerr 3.5.2 security patch was deployed and verified healthy from [PR #20](https://github.com/Jestel2/Docker/pull/20), merge `bd50fe9f2aff0c49af0363567283b2a87a671128`. [Upstream release](https://github.com/seerr-team/seerr/releases/tag/v3.5.2).

Sonarr, Radarr, Prowlarr and Seerr use their own containers on the management bridge and retain ports 8989, 7878, 9696 and 5055. qBittorrent and FlareSolverr share Gluetun's network namespace. qBittorrent remains bound to `tun0`. Gluetun retains its firewall and LAN exception. Prowlarr uses Gluetun's HTTP proxy on internal port 8888 for external indexer requests; local application addresses bypass that proxy. The proxy has no host port. Existing additional published ports 9898, 7879 and 9697 are preserved pending identification.

Seerr's default Sonarr and Radarr roots are `/truenas/Media/TV_Shows` and `/truenas/Media/Videos`. Existing mount aliases remain available for the older library. New requests use the existing HD - 720p/1080p profile.

Recyclarr 8.8.1 uses a disposable container invoked by `arr-recyclarr.timer` daily at 03:25 America/New_York plus up to ten minutes jitter. Its Git-managed YAML preserves all six existing profile identities in each Arr app, quality memberships and disabled upgrades. Remux and Raw-HD remain disabled. HD 720p sizes are capped at 20 MB/minute, with 12 preferred; HD 1080p at 35 MB/minute, with 20 preferred. A 120-minute 1080p movie therefore has about a 4.2 GB ceiling. BR-DISK has score -10000 with minimum custom-format score 0. Existing executable and Gold Rush release-title filters remain in Sonarr. No quality sync triggers searches or upgrades of existing files. [Configuration reference](https://recyclarr.dev/reference/configuration/quality-definition/).

Cleanuparr 2.11.0 is installed with its WebUI bound to host loopback at `127.0.0.1:11011`. It receives no media volume mount. Account setup and queue automation are now active after managed authentication and dry-run verification. After bootstrap, the conservative policy is a 15-minute scan and 96 strikes (approximately 24 hours) for errored downloads and stalled public downloads below 100% completion, resetting strikes on progress. Private torrent deletion, global metadata cleanup, failed-import cleanup, DownloadCleaner and forced import stay disabled. Cleanuparr's native metadata rule deletes globally without a privacy filter, so it requires a separate policy decision before activation. Internet connectivity checks prevent outage-driven strikes. Bootstrap starts in dry run; inspect its activity before invoking `cleanup --live`. [Queue cleaner documentation](https://cleanuparr.github.io/docs/configuration/queue-cleaner/).

## Managed credentials and verified activation

1Password remains authoritative. The administrator added both integration fields and corrected the qBittorrent password. Managed downloader and Cleanuparr admin authentication are now verified. The initial rejected write and password mismatch are retained below as historical evidence. The service account retains its existing read access; no password values were copied into Git, notes or temporary files and no application password was changed.

Required fields in `op://JesterTek/ARR Stack`:

- `QBITTORRENT_WEBUI_PASSWORD`: the current qBittorrent admin password, or a newly coordinated managed rotation.
- `CLEANUPARR_ADMIN_PASSWORD`: a dedicated admin password for Cleanuparr.

The service account needs vault edit permission only if bot is to create or rotate these managed fields. Alternatively, an administrator can add them directly in 1Password. Never paste their values into chat. The existing PBKDF2 field cannot authenticate new API integrations.

Native PIA port forwarding is active on CA Montreal after authenticated port synchronization and an external TCP reachability check. Git includes `arr-qbit-port-sync.service` and `.timer`; the service passed with Result=success/exit 0 and the timer is enabled. The helper reads Gluetun's `/gluetun/forwarded_port` from the host bind mount, verifies VPN health and qBittorrent's `tun0` binding, and changes only its listening-port settings through the authenticated API. It turns off random port selection and UPnP. It performs no torrent deletion.

Activation and recovery checks:

1. Run `sudo -n python3 scripts/arr-maintenance.py qbit-auth` on ddocker from the stack directory. Resolve any centrally managed password mismatch before proceeding.
2. Set nonsecret `PIA_REGION=CA Montreal`, `PIA_PORT_FORWARD_ONLY=true` and `VPN_PORT_FORWARDING=on` in the managed runtime environment; reflect the activation in `vars/arr.yml` and Git. CA Montreal was verified present with port-forward-capable OpenVPN servers in Gluetun's live server database. [PIA forwarding reference](https://github.com/qdm12/gluetun-wiki/blob/main/setup/providers/private-internet-access.md).
3. Recreate Gluetun, qBittorrent and FlareSolverr together during the authorized maintenance window. Wait for healthy VPN and a current forwarded-port file.
4. Run `sudo -n python3 scripts/arr-maintenance.py port-sync`, compare the assigned/listening ports, validate P2P reachability, then enable `arr-qbit-port-sync.timer`. Preserve authentication and the kill switch.
5. Run `sudo -n python3 scripts/arr-maintenance.py cleanup`, inspect dry-run activity, then `cleanup --live` after confirming only the intended stale jobs are targeted. Keep WebUI access local or use a verified SSH tunnel; no public proxy has been configured.

## Deployment and verification

Configuration changes must be committed, reviewed and merged before deployment. Validate the candidate with `python3 scripts/validate-compose.py stacks/arr-stack/docker-compose.yml`; CI checks namespace separation, port ownership and pinned images. Recyclarr preview was successfully executed against live Arr APIs before deployment.

Pull pinned images before stopping applications. Keep `/opt/docker-stacks/arr-stack/maintenance-20261112-optimization/` root-only. Retain the old Compose file and offline application configuration/database backup there. Backups include existing credentials and stay on the host, outside Git. Preserve torrent resume state and media files; do not prune images or volumes.

Stop the affected services, take the backup, install merged Compose/scripts/Recyclarr YAML, and run `arr-maintenance.py seerr-paths` only while Seerr is stopped. Start Gluetun and wait for health, then start qBittorrent, FlareSolverr and the management apps. Run `arr-maintenance.py rewire` to update and test downloader addresses, Prowlarr application URLs and its FlareSolverr endpoint. It queues ApplicationIndexerSync to replace the old localhost indexer URLs. Run `arr-maintenance.py check` to verify library counts, profile safeguards and downloader integrations, then the initial Recyclarr sync and the same check again. Install the systemd units; enable the Recyclarr timer only after a successful sync. Leave port-sync disabled while forwarding is off.

Rollback requires stopping affected services before restoring the prior Compose and offline configuration snapshot. Restore the pre-network Seerr settings alongside the other API address changes, recreate Gluetun and the namespace-sharing clients, then verify the original integrations. Disable the new timers during rollback. Seerr's earlier 3.5.1 archive/image is retained for emergency patch rollback, but the preferred network rollback keeps patched 3.5.2.

## Existing-library migration plan

Live inventory before this rollout: Sonarr 314 series, 223 on legacy paths; Radarr 2271 movies, 2156 on legacy paths. `/mnt/Media/Videos` had approximately 90 MiB free and reported 100% full. `/mnt/Jestertek` had approximately 35 TiB free. This rollout does not move or delete existing media, change TrueNAS datasets or change Plex/Jellyfin libraries.

Migrate in small batches through supported Sonarr/Radarr root-folder moves after verifying source access, destination capacity and playback visibility from plextacular. Choose a small completed show/movie first; copy/verify files and metadata, scan Jellyfin/Plex and verify playback, then approve retirement of the source separately. Keep source files until verification. Preserve season/episode numbering and release filters for Gold Rush; its missing S06E15 onward is a source/download availability problem, not proof of a completed library repair.

Hardlinks were already enabled in both Arr apps. Verify actual filesystem/dataset behavior with a small controlled test before claiming links work across the CIFS share. A shared container mount alone does not prove hardlink support. Avoid broad media moves and do not change TrueNAS configuration as part of this optimization.


## Verified rollout result — 2026-11-12 19:15 UTC

Deployment is complete for Seerr, management networking and Recyclarr. Configuration is merged through [PR #23](https://github.com/Jestel2/Docker/pull/23), commit `57fb621bee6ceb136904f17d821e7706ccbe4071`; [PR #21](https://github.com/Jestel2/Docker/pull/21) contains the topology and maintenance setup, and [PR #22](https://github.com/Jestel2/Docker/pull/22) the HTTP helper correction and regression test. CI passed; the port-status-file review finding was corrected and its thread resolved.

| Check | Observed result |
| --- | --- |
| Core containers | All eight deployed containers running; Gluetun and Seerr healthy |
| Seerr | 3.5.2; Sonarr/Radarr connection tests return HTTP 200; both defaults use TrueNAS |
| VPN boundary | qBittorrent and FlareSolverr share the new Gluetun namespace; qBittorrent still bound to tun0 |
| Indexer proxy | Proxy egress matches the VPN and differs from host egress |
| Prowlarr | Application sync completed; 1337x test passed; no current health warnings |
| Long-failing sources | Uindex and Magnet Cat disabled in Prowlarr and Arr; their retained Arr URLs corrected from localhost to prowlarr |
| Library preservation | Sonarr 314 series, Radarr 2271 movies; six existing profile IDs in each |
| Quality policy | HD size caps 20/35 MB per minute verified through native APIs; BR-DISK -10000 in every profile; upgrades and Remux/Raw-HD disabled |
| Recurrence | Recyclarr timer enabled; daily 03:25 America/New_York plus jitter; repeat sync reports all settings up to date |
| Recovery | Root-only offline configuration archive passed gzip integrity validation |
| Cleanuparr | 2.11.0 running on loopback 11011; account setup incomplete and automation inactive |
| Port forwarding | Off; port-sync timer disabled pending centrally managed downloader authentication |

Recyclarr instance names must be globally unique across app types: `sonarr-homelab` and `radarr-homelab`. The earlier duplicate names caused the CLI to skip both while returning zero; configuration validation now checks uniqueness and the sync helper verifies the resulting native Arr policy. An immediate first read after initial sync showed old size values; subsequent native API reads and an idempotent repeat sync verified the desired values.

At the 19:15 UTC verification, both required plaintext integration fields were absent and the managed write was rejected. The subsequent administrator update and credential verification are recorded below.

Gold Rush S06E15–19 remain missing. The E15/E16 replacement jobs still have zero bytes and no metadata at verification time. Service connectivity and a successful search/grab are not proof of a completed import. Continue with verified episode-title filtering and source availability checks; do not import partial or misnumbered files.

## Initial managed credential follow-up — 2026-11-12 (historical)

Both integration fields now exist in the Secure Note `ARR Stack` in the `JesterTek` vault and are readable by the existing service account. The remaining blocker is a qBittorrent password mismatch, rather than missing fields. Sonarr and Radarr continue to authenticate with their existing stored credentials. Cleanuparr setup and cleanup automation remain inactive; PIA forwarding remains off and the port-sync timer disabled.

The authentication diagnostic also exposed a Python name collision: the `http` helper hid the imported `http.cookiejar` package. [PR #25](https://github.com/Jestel2/Docker/pull/25), merged as `80062e5d2721e7eaf1111e09513615050a3aee26`, imports `CookieJar` directly. Two local HTTP integration tests cover the actual managed downloader login, its session cookie and rejected credentials. CI and automatic review passed; the deployed helper SHA256 is `ebabc92e4e3eadc838eaf0a3464cdb3c321849eac5ae8d5a96de71e43b6be667`. This helper-only deployment did not restart containers or change application passwords.

## Verified activation — 2026-11-12 22:01 UTC

Managed qBittorrent authentication passes and protected preferences are readable. Current qBittorrent returns HTTP 204 with a session cookie on successful login. [PR #27](https://github.com/Jestel2/Docker/pull/27), merge `16e87f90157680befef7ae5a1373dc72ec456979`, accepts current 204 and legacy 200/Ok responses and verifies the authenticated session. Local HTTP integration tests exercise both responses, rejected passwords and a missing cookie; CI and automatic review passed. Deployed helper SHA256: `874353acbba60127a8f0dc4ceaa7f67740f9358369e1b13669be1959bb5b9d75`.

[PR #28](https://github.com/Jestel2/Docker/pull/28), merge `0ad66b07ca18fd72fbb85ccfc516785e99832b45`, configures `PIA_REGION=CA Montreal`, `PIA_PORT_FORWARD_ONLY=true` and `VPN_PORT_FORWARDING=on` in the managed template and sanitized example. VPN credentials were supplied to Compose in process memory from 1Password. Only Gluetun, qBittorrent and FlareSolverr were recreated; all 14 torrent entries survived. The template is installed on ddocker for subsequent managed redeploys.

The initial Montreal connection failed TLS negotiation with stale built-in endpoints. The supported Gluetun updater refreshed PIA's server cache in the existing persistent bind mount, using the same pinned image without credentials, and Gluetun connected successfully afterward. [Server-cache update procedure](https://github.com/qdm12/gluetun-wiki/blob/main/setup/servers.md#update-using-the-command-line). Treat cache files as runtime data, not Git content. The prior template and offline qBittorrent configuration/resume archive remain root-only in the existing recovery directory.

| Check | Observed result |
| --- | --- |
| Native forwarding | Healthy CA Montreal tunnel; PIA assigned port 51689 and Gluetun opened it through tun0 |
| Listening port | qBittorrent port 51689 matched the forwarded-port file; tun0 binding retained; random port and UPnP disabled |
| Inbound access | TCP connection from plextacular outside the VPN to 140.228.24.233:51689 succeeded |
| P2P | Connected; DHT populated and download traffic observed |
| Recurrence | Port-sync service Result=success/exit 0; timer enabled and active; Recyclarr timer remains active |
| Cleanuparr | Managed admin login passed; dry-run scans reviewed; queue cleaner live, every 15 minutes, 96 strikes |
| First live scan | Three stalled-strike events; no error or removal events observed |
| Safeguards | Public-only stall rule, reset on progress; private deletion, failed-import cleanup, metadata cleanup, forced import and DownloadCleaner disabled |
| Other automation | Proactive Seeker search disabled and both Seeker instances disabled |
| Service health | All ARR containers running; Gluetun/Seerr healthy; downloader tests passed; Prowlarr health empty; Plex/Jellyfin/Plextreme healthy |

Assigned IP/port values are this verification's observations and can change on a later VPN session; the timer reads the current status file. Gold Rush E15/E16 replacements still had no metadata or downloaded bytes. No completed episode import, media migration or TrueNAS change is claimed.
