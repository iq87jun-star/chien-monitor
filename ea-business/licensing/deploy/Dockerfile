FROM node:22-alpine

WORKDIR /app

# Only package.json + source; no secrets are baked in (provided via env at run).
COPY package.json ./
COPY server.js webhook.js keygen.js ./

# Persisted license store lives on a mounted volume, not in the image.
ENV LICENSE_DB_PATH=/data/licenses.json
ENV LICENSE_OUTBOX_PATH=/data/issued-keys.log
VOLUME ["/data"]

EXPOSE 8080 8090

# Default: verify server. Override command to run the webhook instead.
CMD ["node", "server.js"]
