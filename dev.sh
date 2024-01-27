#!/bin/bash

DOCKER_CMD="${DOCKER_CMD:-docker}"
CONTAINER_NAME="${CONTAINER_NAME:-vintage-pi-tv-dev}"


if ! which "${DOCKER_CMD}" > /dev/null 2> /dev/null; then
    echo "Please install Docker to run dev script."
    exit 1
fi

DO_REBUILD=
if [ "$1" == "--rebuild" ]; then
    DO_REBUILD=1
    shift 1
fi

if [ "$DO_REBUILD" -o -z "$(docker images -q "${CONTAINER_NAME}" 2> /dev/null)" ]; then
    echo "Building container ${CONTAINER_NAME} now."
    docker build -t "${CONTAINER_NAME}" -f docker/Dockerfile .
fi

docker run --rm -it -v "${PWD}:/app" -v "${PWD}/videos:/videos" -p 8000:8000 "${CONTAINER_NAME}" "$@"
