# Keep the verified Soketi/uWS application and its Node24 native ABI. The build
# controller checks the source image ID before copying these application files.
FROM local/soketi:1.6.1-node24-uws71-trixie AS application

# Pin the published Node24 patch within the existing Debian Trixie runtime.
FROM node:24.22.2-trixie-slim@sha256:0820eaa85e07d0490446dd01d14707e17e6108a36988cf374899cd057eb3812d
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
COPY --from=application /app /app
WORKDIR /app
EXPOSE 6001
ENTRYPOINT ["node", "/app/bin/server.js", "start"]
