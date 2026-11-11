# Carry the reviewed Keep application/venv onto a patched CPython 3.13 runtime.
# Precondition: both pinned images are available; no production state or secrets
# may enter the build context. Keep's compiled dependencies remain in the same
# Python minor series and musl platform; imports/migration/API probes must pass.
FROM us-central1-docker.pkg.dev/keephq/keep/keep-api@sha256:31a732db788d296aa9c570b502718bac3de4bb3b6be5df38248ef091688895ba AS application
FROM python:3.13.18-alpine3.23@sha256:a0a92a22f3de839a0000df171de555624abe5b8ab235f818004ec64310e25fee
RUN apk add --no-cache bash libstdc++ libffi tzdata ca-certificates && apk upgrade --no-cache
RUN addgroup -g 1000 keep && adduser -D -u 1000 -G keep keep
COPY --from=application /venv /venv
COPY --from=application /app /app
# Preserve startup behavior while removing shell tracing of runtime arguments.
RUN sed -i '/^set -x$/d' /venv/lib/python3.13/site-packages/keep/entrypoint.sh && chmod 0755 /venv/lib/python3.13/site-packages/keep/entrypoint.sh
ENV PATH="/venv/bin:${PATH}" VIRTUAL_ENV=/venv PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1 PYTHONHASHSEED=random EE_PATH=ee
WORKDIR /app
USER keep
EXPOSE 8080
ENTRYPOINT ["/venv/lib/python3.13/site-packages/keep/entrypoint.sh"]
CMD ["gunicorn", "keep.api.api:get_app", "--bind", "0.0.0.0:8080", "--workers", "4", "-k", "uvicorn.workers.UvicornWorker", "-c", "/venv/lib/python3.13/site-packages/keep/api/config.py", "--preload"]
