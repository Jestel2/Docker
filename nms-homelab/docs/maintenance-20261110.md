# Home LibreNMS and MariaDB maintenance — 2026-11-10

The running November 10 stack used LibreNMS26.6.1 and MariaDB10.5.29. MariaDB10.5
is out of community maintenance. The selected target is LibreNMS26.10.2 with
MariaDB11.4.13LTS, pinned to the tested registry digests in Compose.

## Live configuration preserved

- Stack root `/opt/docker-stacks/nms-stack`, host networking, existing container
  names and database credentials. Runtime secret values remain managed outside Git.
- Live `lower_case_table_names=0`. The older Git value1 does not describe the
  actual running database and must not be applied to either data directory.
- SwitchLookup, Smokeping RRD, composer-plugin, Oxidized, proxy and session settings.
  Login currently uses the `mysql` mechanism. The mounted optional SAML dependency
  file was not installed in the running26.6.1 image; no SAML reconfiguration is part
  of this maintenance. Local and public `/login` returnedHTTP200 before maintenance.

## Verification already performed

A consistent logical dump was restored into an isolated MariaDB11.4.13 container:
164tables,14devices,390migrations, case mode0, all tables checkedOK. LibreNMS26.10.2
migrations on another isolated restore advanced to408migrations and retained all
14devices; table checks remainedOK. All five SwitchLookupPHPfiles passed syntax
checks under the candidatePHP8.4.27 runtime. Test containers/networks were removed;
production data was unchanged by these tests.

## Cutover

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
the target database andHTTP200login gates pass does the script replace the live
`compose.yaml` with the reviewed desired state. Check the root-readable
`maintenance-20261110/status.json` for `cutover_verified`. A transient systemd unit
can keep the operation alive across an SSH disconnect; inspect that unit and status
before any retry.

On a normal exception, the script attempts the saved image IDs and original
database directory, then verifies its original counts and login. An interruption
requires inspecting state before continuing; the one-time script deliberately
refuses an existing target directory. Recovery Compose contains placeholders only.
It requires the same managed runtime secret environment as the normal stack.
Never point MariaDB10.5 at the11.4data directory.

## Recovery checks

Verify database11.4.13, app/dispatcher26.10.2, all14devices, migration count at
least408 and case mode0. Run LibreNMS validation, then confirm automatic scheduler
heartbeats and fresh polling over more than one interval. Verify both local
`http://127.0.0.1:8000/login` and publicHTTPSlogin, SwitchLookup, Smokeping mounts,
Redis, Oxidized, and the existing alert delivery path. An unauthenticatedHTTP200
does not prove a user completed an interactive login.

Retain the original database directory, prior image IDs and recovery metadata
until the normal backup and restore checks have passed. Do not delete them as
part of patching. No frozen PAN-OS automation or other stacks are changed here.
