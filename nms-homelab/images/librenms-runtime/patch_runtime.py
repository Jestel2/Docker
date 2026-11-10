"""Patch the pinned initializer and supervise Laravel's native scheduler.

Preconditions: exact known upstream initializer; root-owned image build.
Outputs: executable checkers, traversable cron directories and one scheduler
worker owned by librenms. Daily maintenance remains in cron. The dispatcher
sidecar returns before service creation, preserving a single scheduler owner.

Laravel's sub-minute schedule:run can span a whole minute. BusyBox cron skips a
still-running job on the next minute, so a five-minute heartbeat can miss its
six-minute TTL. schedule:work launches each minute and manages child processes;
existing Laravel locks and task definitions retain their authority.
"""
from pathlib import Path

path = Path("/etc/cont-init.d/07-svc-cron.sh")
source = path.read_text()
assert source.count("mkdir -m 0644 -p") == 1
assert source.count("chmod -R 0644") == 1
source = source.replace("mkdir -m 0644 -p", "mkdir -m 0755 -p")
source = source.replace("chmod -R 0644 ${CRONTAB_PATH}",
    'find ${CRONTAB_PATH} -type d -exec chmod 0755 {} \\;\nfind ${CRONTAB_PATH} -type f -exec chmod 0644 {} \\;')
cron = 'echo "* * * * * php /opt/librenms/artisan schedule:run --no-ansi --no-interaction > /dev/null 2>&1" >>${CRONTAB_PATH}/librenms'
assert source.count(cron) == 1
source = source.replace(cron, "# Scheduler execution belongs to the supervised worker.")
source = source.replace('echo "Creating LibreNMS cron artisan schedule:run"',
                        'echo "Creating supervised LibreNMS scheduler worker"')
source += """
# Daily maintenance remains in cron; scheduler ownership is separate.
mkdir -p /etc/services.d/scheduler
cat >/etc/services.d/scheduler/run <<'SCHEDULER_RUN'
#!/usr/bin/with-contenv bash
set -e
cd /opt/librenms
exec s6-setuidgid librenms php artisan schedule:work --no-ansi --no-interaction
SCHEDULER_RUN
chmod +x /etc/services.d/scheduler/run
"""
path.write_text(source)
assert "mkdir -m 0755 -p" in path.read_text()
for name in ["dynamic_check_requirements.py", "check_requirements.py"]:
    (Path("/opt/librenms/scripts") / name).chmod(0o755)
