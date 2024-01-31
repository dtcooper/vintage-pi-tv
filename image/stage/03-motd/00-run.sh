#!/bin/bash -e

sed -i 's/^#\?\(PrintLastLog\).*$/\1 no/' "${ROOTFS_DIR}/etc/ssh/sshd_config"
rm -v "${ROOTFS_DIR}/etc/motd" "${ROOTFS_DIR}/etc/update-motd.d/"*

install -vm 755 files/10-welcome "${ROOTFS_DIR}/etc/update-motd.d/"
install -vm 755 files/20-system "${ROOTFS_DIR}/etc/update-motd.d/"
