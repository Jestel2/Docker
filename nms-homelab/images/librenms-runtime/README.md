# LibreNMS 26.10.2 runtime compatibility

The November 10 upstream image includes setuptools 84 without pkg_resources.
Both bundled requirement checkers still import that removed API. The image also
creates /var/spool/cron/crontabs with mode 0644, preventing the librenms user from
traversing the directory when cron starts PHP.

Build this directory as local/librenms:26.10.2-runtimefix-20261110-v3 on the NMS host.
The pinned upstream image, public packaging 25.0 parser, and importlib.metadata
replace both obsolete checks. Installed versions, transitive dependencies, markers
and requested extras remain validated. A standalone build script supports the host's legacy builder and restores
executable permissions on both copied checkers. The cron initialization keeps directory
mode 0755 and file mode 0644. Application, database and data paths are unchanged.

After review/merge, build and run both checker commands and pip check without
production mounts. Verify missing-package exit 1 and version-conflict exit 2.
Recreate only librenms and dispatcher using the existing runtime secret
environment. Retain the prior image IDs and MariaDB recovery directories.
Verify validation, fresh polling, local/public login and automatic scheduler
heartbeat beyond its six-minute expiration. Do not manually run schedule:run
during that observation. Check the image ID after container recreation.

When an upstream version fixes these problems, remove this derived image after
the same checks rather than carrying the patch indefinitely.

BusyBox cron skips the following launch when Laravel's sub-minute schedule:run
remains active. A single s6-supervised schedule:work process now owns scheduling
in the main app container, using the native Laravel command and librenms user.
Daily cron maintenance remains; sidecars do not create the worker. Verify renewal
at consecutive five-minute boundaries and after more than six minutes, and
verify there is one worker with no schedule:run entry left in the crontab.
