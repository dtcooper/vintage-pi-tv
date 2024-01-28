#!/bin/bash

supervisord -c /etc/supervisor/supervisord.conf

pushd /app > /dev/null || exit 1
PATH="$(poetry env info -p)/bin:${PATH}"
export PATH
popd > /dev/null || exit 1

exec "$@"
