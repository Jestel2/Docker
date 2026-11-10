# Upstream application remains pinned; this image fixes runtime compatibility.
FROM librenms/librenms:26.10.2@sha256:66f586a84355b6c80758e373aaa7c0b230284d1d22588b29b3706540041e2806
USER root
RUN python3 -m pip install --no-cache-dir --break-system-packages packaging==25.0
COPY requirement_validation.py dynamic_check_requirements.py check_requirements.py /opt/librenms/scripts/
COPY patch_runtime.py /usr/local/bin/librenms-runtime-patch.py
# Use an explicit script because the NMS host's legacy builder skips RUN heredocs.
RUN python3 /usr/local/bin/librenms-runtime-patch.py
# Invoke exactly as the PHP validator/legacy wrapper do, including executable bits.
RUN /opt/librenms/scripts/dynamic_check_requirements.py -v \
 && /opt/librenms/scripts/check_requirements.py -v \
 && python3 -m pip check
