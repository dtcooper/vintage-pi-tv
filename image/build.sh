#!/bin/sh

if [ -z "$RUN_VINTAGE_PI_TV_BUILD_SCRIPT" ]; then
    cat <<EOF

WARNING: This script should ONLY run inside a clean systemd-nspawn Raspberry Pi
OS container, inside the dtcooper/rpi-image-modifier GitHub action.

If you don't know what this means, you probably don't want to run this script.

If you're *SURE* you know what you're doing, run this script via the following,

    \$ RUN_VINTAGE_PI_TV_BUILD_SCRIPT=1 ${0}

EOF
    exit 1
fi

set -e

REPO_DIR=/mounted-github-repo/
FILES_DIR="${REPO_DIR}/image/files"

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    libmpv2 \
    mpv \
    udiskie

cp -v "${FILES_DIR}/99-udisks2.rules" /etc/udev/rules.d/
cp -v "${FILES_DIR}/50-udiskie.rules" /etc/polkit-1/rules.d/
cp -v "${FILES_DIR}/udiskie.service" /etc/systemd/system/

addgroup --system storage
adduser pi storage

mkdir -p /usr/local/lib/vintage-pi-tv-sys-mods
cp -v "${FILES_DIR}/resize_partitions.sh" /usr/local/lib/vintage-pi-tv-sys-mods/
sed -i 's|init=/usr/lib/raspberrypi-sys-mods/firstboot|init=/usr/local/lib/vintage-pi-tv-sys-mods/resize_partitions.sh|' /boot/firmware/cmdline.txt
systemctl enable udiskie.service

cp -v "${REPO_DIR}/sample-config.toml" /boot/firmware/vintage-pi-tv-config.toml
cp -v "${REPO_DIR}/sample-videos-db.toml" /boot/firmware/vintage-pi-tv-videos-db.toml

curl -L https://install.python-poetry.org | POETRY_HOME=/opt/poetry python3
cp -v "${FILES_DIR}/poetry.sh" /etc/profile.d/
su - pi -c "git clone --branch '${GITHUB_REF_NAME}' file:///mounted-github-repo/ vintage-pi-tv"
if [ "${GITHUB_REF_TYPE}" = 'tag' ]; then
    su - pi -c "cd vintage-pi-tv ; rm -rf .git ; echo '${GITHUB_REF_NAME}' > version.txt"
else
    su - pi -c "cd vintage-pi-tv ; git remote set-url origin 'https://github.com/${GITHUB_REPOSITORY}.git'"
fi
su - pi -c "cd vintage-pi-tv ; poetry config virtualenvs.in-project true"
su - pi -c "cd vintage-pi-tv ; poetry install --without=dev"
