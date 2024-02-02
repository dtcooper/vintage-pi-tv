#!/bin/bash

# Helper script to develop Vintage Pi TV in a controlled environment using
# Docker and your web browser.

cd "$(dirname "$0")" || exit

DOCKER_CMD="${DOCKER_CMD:-docker}"
CONTAINER_NAME="${CONTAINER_NAME:-vintage-pi-tv-dev}"
_PI_LOOKUP_FILE=/sys/firmware/devicetree/base/model
_CMD="$0"

if [ -e '/.dockerenv' ]; then
    echo "Won't run inside of Docker."
fi

verify_cmd_exists () {
    if ! which "${1}" 2> /dev/null > /dev/null; then
        echo "${2:-The '$1' command} is required to run this script"
        exit 1
    fi
}

verify_cmd_exists "${DOCKER_CMD}" Docker

do_help_and_exit () {
    cat <<EOF
Usage: ${_CMD} [-h] [-r] [-p <int>]

Develop Vintage Pi TV in a Docker container with noVNC

Options:
    -r, --rebuild           Force a rebuild of the Docker container
    -p <int>, --port <int>  Port to bind the HTTP server to
    -a, --audio             Attempt to enable sound via Pulseaudio
    -b, --browser           Open web browser after starting container
    -f, --force             Force running of this tool, even on a Raspberry Pi
    -h, --help              Show this help screen
EOF
    exit "${1:-0}"
}

DO_REBUILD=
PORT=8000
DO_AUDIO=
DO_OPEN_BROWSER=
DO_FORCE=

# If first argument starts with a hyphen, it's meant for this program
while [ "${1:0:1}" = '-' ]; do
  case "$1" in
        -r|--rebuild)
            DO_REBUILD=1
        ;;
        -p|--port)
            PORT="${2}"
            shift 1
        ;;
        -a|--audio)
            DO_AUDIO=1
        ;;
        -b|--browser)
            DO_OPEN_BROWSER=1
        ;;
        -f|--force)
            DO_FORCE=1
        ;;
        -h|--help)
            do_help_and_exit
        ;;
        --)
            shift 1
            break
        ;;
        *)
            echo "Error: Unknown argument to ${_CMD}: $1 (options need to be separated)"
            echo
            do_help_and_exit  1
        ;;
  esac

  shift 1
done

if [ -z "${DO_FORCE}" ] && [ -e "${_PI_LOOKUP_FILE}" ] && grep -qi 'raspberry pi' "${_PI_LOOKUP_FILE}"; then
    echo "Won't run on a Raspberry Pi. Use -f / --force option to override this."
    exit 1
fi

DOCKER_EXEC=(
    "${DOCKER_CMD}" run --rm -it
        -v "${PWD}:/app"
        -v "${PWD}/videos:/videos"
        -v "${PWD}/docker/daemons.conf:/etc/supervisor/conf.d/daemons.conf"
        -v "${PWD}/docker/nginx.conf:/etc/nginx/sites-enabled/default"
        -v "${PWD}/docker/entrypoint.sh:/entrypoint.sh"
        -p "${PORT}:8000"
)

if [ "${DO_REBUILD}" ] || [ -z "$("${DOCKER_CMD}" images -q "${CONTAINER_NAME}" 2> /dev/null)" ]; then
    echo "Building container ${CONTAINER_NAME} now."
    "${DOCKER_CMD}" build -t "${CONTAINER_NAME}" -f docker/Dockerfile .
fi

if [ "${DO_AUDIO}" ]; then
    DO_AUDIO_SUCCESS=

    case "$(uname)" in
        Darwin)
            verify_cmd_exists pulseaudio 'Pulseaudio'
            if ! pulseaudio --check 2> /dev/null > /dev/null; then
                echo 'NOTE: Attempting to start Pulseaudio daemon on macOS.'
                echo '      Use the following command to stop it: $ pulseaudio --kill'
                pulseaudio -n --load='module-native-protocol-tcp auth-ip-acl=127.0.0.1 auth-anonymous=1' \
                    --load=module-coreaudio-detect --daemonize=true --exit-idle-time=-1 2> /dev/null
            fi
            if pulseaudio --check 2> /dev/null > /dev/null; then
                DOCKER_EXEC+=('-e' 'PULSE_SERVER=tcp:host.docker.internal')
                DO_AUDIO_SUCCESS=1
            fi
        ;;
        Linux)
            verify_cmd_exists pactl 'Pulseaudio'
            PULSE_SOCKET="$(pactl info 2> /dev/null | grep 'Server String:' | rev| cut -d ' ' -f 1 | rev)"
            if [ "${PULSE_SOCKET}" ] && [ -S "${PULSE_SOCKET}" ]; then
                DOCKER_EXEC+=(
                    '-v' "${PULSE_SOCKET}:/tmp/pulseaudio.socket.host"
                    '-e' 'PULSE_SERVER=unix:/tmp/pulseaudio.socket.host'
                )
                DO_AUDIO_SUCCESS=1
            fi
        ;;
    esac

    if [ -z "${DO_AUDIO_SUCCESS}" ]; then
        echo "WARNING: Unable to get Pulseaudio working. Can't enable audio."
    fi
fi

if [ "${DO_OPEN_BROWSER}" ]; then
    verify_cmd_exists python3 'Python 3'
    ( ( sleep 3.5 ; python3 -m webbrowser \
        -t "http://localhost:${PORT}/?autoconnect=1&resize=remote&reconnect=1&reconnect_delay=1500" \
      ) > /dev/null 2>&1 &);
fi

DOCKER_EXEC+=("${CONTAINER_NAME}" "$@")
echo "${DOCKER_EXEC[@]}"
exec "${DOCKER_EXEC[@]}"
