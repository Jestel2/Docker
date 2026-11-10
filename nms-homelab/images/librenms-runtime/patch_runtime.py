"""Patch the pinned upstream cron initializer and restore checker executability.

Preconditions: exact known upstream initializer; root-owned image build.
Outputs: traversable cron directories at startup and executable checker scripts.
Assertions fail a build when an upstream layout changes; no live data is accessed.
"""
from pathlib import Path

path = Path("/etc/cont-init.d/07-svc-cron.sh")
source = path.read_text()
assert source.count("mkdir -m 0644 -p") == 1
assert source.count("chmod -R 0644") == 1
source = source.replace("mkdir -m 0644 -p", "mkdir -m 0755 -p")
source = source.replace("chmod -R 0644 ${CRONTAB_PATH}",
    'find ${CRONTAB_PATH} -type d -exec chmod 0755 {} \\;\nfind ${CRONTAB_PATH} -type f -exec chmod 0644 {} \\;')
path.write_text(source)
assert "mkdir -m 0755 -p" in path.read_text()
for name in ["dynamic_check_requirements.py", "check_requirements.py"]:
    (Path("/opt/librenms/scripts") / name).chmod(0o755)
