#!/bin/bash -e

cd "$(dirname "$0")"

if [ ! -d pi-gen ]; then
    echo 'WARNING: pi-gen not found, checking out a copy'
    git clone --branch arm64 https://github.com/RPI-Distro/pi-gen.git
fi

cd pi-gen
rm -vf deploy/*
touch stage2/SKIP_IMAGES
ln -sf ../config .

PIGEN_DOCKER_OPTS="\
        -v ./../stage-nodejs:/pi-gen/stage-nodejs \
        -v ./../stage-vintage-pi-tv:/pi-gen/stage-vintage-pi-tv \
        -v ./../..:/pi-gen/stage-vintage-pi-tv/04-install-vintage-pi-tv/files/vintage-pi-tv \
        -e GITHUB_REF_TYPE=copy" \
    ./build-docker.sh

# Gets created with -v arg above, delete it
if [ -d ../stage-vintage-pi-tv/04-install-vintage-pi-tv/files/vintage-pi-tv ]; then
    rmdir ../stage-vintage-pi-tv/04-install-vintage-pi-tv/files/vintage-pi-tv
fi

cd ..

FULL_IMAGE_PATH="$(ls -1 pi-gen/deploy/image_*.img* | head -n 1)"
IMAGE_PATH="${FULL_IMAGE_PATH/#"pi-gen/deploy/image_"}"
mv -v "${FULL_IMAGE_PATH}" "${IMAGE_PATH}"
echo "New image: ${IMAGE_PATH}"
