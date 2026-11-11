# Docker2 SQL Server maintenance — verified 2026-11-11

Production cutover completed at 00:51:05 UTC. SQL Server 2022 Express is 16.0.4315.2 on the pinned image in sqlserver-20261110.yaml. The live Compose is `/opt/docker-stacks/devolutions-server/compose.yaml`, using external volume `devolutions-server_mssql_data_20261110`. The complete cold clone finished, including old diagnostic artifacts. Do not run another clone or one-time rollout against this verified deployment.

Recovery gates passed: ONLINE dvls, all 161 user tables, DBCC CHECKDB, healthy SQL container, DVLS HTTPS 200 on port 5000 and the application's pooled database connection. BIND/DNS and unrelated Docker2 containers stayed active. Interactive user login remains a separate client check.

Native COPY_ONLY/CHECKSUM backups of dvls/master/msdb passed VERIFYONLY; isolated restore on the exact target passed integrity and table count. Express backup compression is unsupported. The original `devolutions-server_mssql_data` volume and original image `sha256:5b7ccec26ee46177037f7c07695f9b18d804e016561cbe79777288f8828d74ca` are retained untouched for rollback. Do not start the older image on upgraded data; use the original volume. Preserve both data sets and native backups until normal post-maintenance backups are verified.

The vendor launch_sqlservr.sh starts sqlservr in the background without forwarding Docker's stop signal. Supported T-SQL SHUTDOWN, without NOWAIT and with automatic restart temporarily disabled, produced a requested-shutdown log and exit255 without a Docker kill. Require that completed shutdown, stopped engine and no OOM before future cold copies. See shutdown-verification.md. Controller systemd completion still requires exit0.

Approximately 10 GiB of September core.sqlservr dumps make a full cold copy slow. A future operational clone may exclude only `log/core.sqlservr.*` while retaining those diagnostics on the original volume; this deployment completed its full clone and does not use the proposed 20261111 volume.

Use explicit tcp:127.0.0.1,1433 for isolated SQL queries. Keep authentication in existing managed container/process environments. Do not print or write credentials, alter VM disks/placement/memory, prune data, change DNS/BIND or modify frozen PAN-OS certificate automation. Root-readable status is `/var/tmp/sqlserver-maintenance-20261110/rollout-status-retry2.json`; unit `sqlserver-rollout-20261111-retry2.service` completed active/exited, success/exit0.
