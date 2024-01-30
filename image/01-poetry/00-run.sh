#!/bin/bash -e

POETRY_VERSION=1.7.1
POETRY_HOME=/opt/poetry

install -vm 644 files/poetry.sh "${ROOTFS_DIR}/etc/profile.d/"

on_chroot <<EOF
curl -L https://install.python-poetry.org | POETRY_HOME="${POETRY_HOME}" POETRY_VERSION="${POETRY_VERSION}" python3
EOF
