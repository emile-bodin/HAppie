# https://contributors.home-assistant.io/apps/guides/dockerfile/
ARG BUILD_FROM=ghcr.io/home-assistant/base:3.24
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-aiohttp

COPY app /app
WORKDIR /app

# s6-overlay (PID 1 in the base image) starts CMD with an empty environment;
# with-contenv passes the container env on, including SUPERVISOR_TOKEN
CMD [ "/usr/bin/with-contenv", "python3", "-u", "/app/main.py" ]

LABEL \
    org.opencontainers.image.title="Home Assistant App: HAppie" \
    org.opencontainers.image.description="Albert Heijn-boodschappenlijst in Home Assistant, met sync naar de AH-app" \
    org.opencontainers.image.source="https://github.com/emile-bodin/HAppie" \
    org.opencontainers.image.licenses="Apache-2.0"
