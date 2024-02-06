#!/bin/bash

echo "# Starting supervisord in container..."
supervisord -c /etc/supervisor/supervisord.conf

pushd /app > /dev/null || exit 1
export PATH="$(poetry env info -p)/bin:${PATH}"
popd > /dev/null || exit 1

echo "\$ $*"
exec "$@"
