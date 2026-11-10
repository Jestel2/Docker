# Upstream application remains pinned; this image fixes runtime compatibility.
FROM librenms/librenms:26.10.2@sha256:66f586a84355b6c80758e373aaa7c0b230284d1d22588b29b3706540041e2806
USER root
RUN python3 -m pip install --no-cache-dir --break-system-packages packaging==25.0
COPY requirement_validation.py dynamic_check_requirements.py check_requirements.py /opt/librenms/scripts/
# Upstream initializes a real cron directory with file permissions. Cron switches
# to librenms before running PHP, so directories must remain traversable.
RUN python3 - <<'PY'
from pathlib import Path
path = Path("/etc/cont-init.d/07-svc-cron.sh")
source = path.read_text()
assert source.count("mkdir -m 0644 -p") == 1
assert source.count("chmod -R 0644") == 1
source = source.replace("mkdir -m 0644 -p", "mkdir -m 0755 -p")
source = source.replace("chmod -R 0644 ${CRONTAB_PATH}",
    'find ${CRONTAB_PATH} -type d -exec chmod 0755 {} \\;\nfind ${CRONTAB_PATH} -type f -exec chmod 0644 {} \\;')
path.write_text(source)
PY
RUN python3 /opt/librenms/scripts/dynamic_check_requirements.py -v \
 && python3 /opt/librenms/scripts/check_requirements.py -v \
 && python3 -m pip check
