#!/bin/sh
# Hosting platforms often mount the data volume owned by root. Fix that, then run the app as an unprivileged user.
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p "${SF_DATA_DIR:-/data}"
  want="$(id -u app)"
  if [ "$(stat -c %u "${SF_DATA_DIR:-/data}")" != "$want" ]; then
    chown -R app:app "${SF_DATA_DIR:-/data}"
  fi
  exec setpriv --reuid=app --regid=app --init-groups "$@"
fi
exec "$@"
