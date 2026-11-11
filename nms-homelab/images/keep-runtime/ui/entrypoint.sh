#!/bin/sh
# The Compose runtime owns authentication configuration. Refuse missing secrets
# before starting Next; never substitute demo credentials or log secret values.
set -eu
if [ -z "${NEXTAUTH_SECRET:-}" ]; then
    echo "Keep UI requires its configured NEXTAUTH_SECRET" >&2
    exit 1
fi
exec node server.js
