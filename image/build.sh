#!/bin/bash

cd "$(dirname "$0")"

if [ ! -d pi-gen ]; then
    echo 'WARNING: pi-gen not found, checking out a copy'
    git clone --branch arm64 https://github.com/RPI-Distro/pi-gen.git
fi

cd pi-gen
touch stage2/SKIP_IMAGES
ln -sf ../config .

PIGEN_DOCKER_OPTS="-v ./../stage:/pi-gen/vintage-pi-tv -v ./../..:/pi-gen/vintage-pi-tv/04-install-vintage-pi-tv/files/vintage-pi-tv" ./build-docker.sh
