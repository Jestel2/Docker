# Home LibreNMS and MariaDB maintenance — 2026-11-10

The running November 10 stack used LibreNMS 26.6.1 and MariaDB 10.5.29. MariaDB 10.5
is out of community maintenance. The selected target is LibreNMS 26.10.2 with
MariaDB 11.4.13 LTS. MariaDB is pinned to its tested registry digest; LibreNMS
uses the reviewed derived runtime image built from the pinned upstream digest.

## Live configuration preserved

- Stack root `/opt/docker-stacks/nms-stack`, host networking, existing container
  names and database credentials. Runtime secret values remain managed outside Git.
- Live `lower_case_table_names=0`. The older Git value 1 does not describe the
  actual running database and must not be applied to either data directory.
- SwitchLookup, Smokeping RRD, composer-plugin, Oxidized, proxy and session settings.
  Login currently uses the `mysql` mechanism. The mounted optional SAML dependency
  file was not installed in the running 26.6.1 image; no SAML reconfiguration is part
  of this maintenance. Local and public `/login` returned HTTP 200 before maintenance.

## Verification already performed

A consistent logical dump was restored into an isolated MariaDB 11.4.13 container:
164 tables, 14 devices, 390 migrations, case mode 0, all tables checked OK. LibreNMS 26.10.2
migrations on another isolated restore advanced to408 migrations and retained all
14 devices; table checks remained OK. All five SwitchLookup PHP files passed syntax
checks under the candidate PHP 8.4.27 runtime. Test containers/networks were removed;
production data was unchanged by these tests.

## Cutover

Before a first migration, build `images/librenms-runtime` as
`local/librenms:26.10.2-runtimefix-20261110-v2` on NMS and verify its two Python
checkers and `pip check`. The migration preflight requires that exact image
reference for both application services. This fixes the upstream removed
`pkg_resources` imports and cron directory permissions. An already migrated
host must recreate only the app and dispatcher; do not rerun the one-time
MariaDB migration or change its database directories.

Do not run ordinary Compose against an unseeded `db-11.4` directory. The long bind
syntax has `create_host_path:false` to prevent creating an empty database path.

Use the reviewed `scripts/migrate-nms-20261110.py` as root on the verified `nms`
host, passing the reviewed Compose rendered as JSON. It validates this lab's
baseline and the exact target digests, records sanitized recovery state, pauses
LibreNMS writers, streams a fresh logical dump into the separate database path,
checks row/migration counts and table integrity, and stops the seed container
cleanly before cutover. Credentials travel through existing container/child-process
environments; SQL dumps and authentication values are not written to files or
printed. LibreNMS and its dispatcher have downtime during this operation.

The original `/opt/docker-stacks/nms-stack/db` directory stays intact. Only after
the target database andHTTP 200 login gates pass does the script replace the live
`compose.yaml` with the reviewed desired state. Check the root-readable
`maintenance-20261110/status.json` for `cutover_verified`. A transient systemd unit
can keep the operation alive across an SSH disconnect; inspect that unit and status
before any retry.

On a normal exception, the script attempts the saved image IDs and original
database directory, then verifies its original counts and login. An interruption
requires inspecting state before continuing; the one-time script deliberately
refuses an existing target directory. Recovery Compose contains placeholders only.
It requires the same managed runtime secret environment as the normal stack.
Never point MariaDB 10.5 at the 11.4 data directory.

## Recovery checks

Verify database 11.4.13, app/dispatcher 26.10.2, all 14 devices, migration count at
least 408 and case mode 0. Run LibreNMS validation, then confirm automatic scheduler
heartbeats and fresh polling over more than one interval. Verify both local
`http://127.0.0.1:8000/login` and public HTTPS login, SwitchLookup, Smokeping mounts,
Redis, Oxidized, and the existing alert delivery path. An unauthenticatedHTTP 200
does not prove a user completed an interactive login.

Retain the original database directory, prior image IDs and recovery metadata
until the normal backup and restore checks have passed. Do not delete them as
part of patching. No frozen PAN-OS automation or other stacks are changed here.
