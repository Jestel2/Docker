# Preserve the upstream standalone Next application on patched Node 24.
# Application files are upstream build artifacts, never live state or secrets.
# Native dependencies must import and the standalone server must pass isolated
# startup/auth-page checks before this runtime may replace the existing UI.
FROM us-central1-docker.pkg.dev/keephq/keep/keep-ui@sha256:0f02405658cabb98e1825e4a9000373178394a0c749420ab2920031c91cea09e AS application
FROM node:24.22.2-alpine3.23@sha256:0efee1e068d21f6edcab7fa8c962fc4ecd50d4e28727bc23963379b63ee318ab
RUN apk add --no-cache gcompat ca-certificates && apk upgrade --no-cache
RUN adduser -D -u 1001 -G nogroup nextjs
COPY --from=application --chown=1001:65533 /app /app
COPY entrypoint.sh /app/entrypoint.sh
# COPY mode is not assumed: the host uses Docker's legacy builder.
RUN chmod 0755 /app/entrypoint.sh
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
USER nextjs
EXPOSE 3000
ENTRYPOINT ["/app/entrypoint.sh"]
