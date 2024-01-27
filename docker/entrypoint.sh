#!/bin/bash

supervisord -c /etc/supervisor/supervisord.conf

pushd /app > /dev/null
export PATH="$(poetry env info -p)/bin:${PATH}"
popd > /dev/null

exec "$@"
