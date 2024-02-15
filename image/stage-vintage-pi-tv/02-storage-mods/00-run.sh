#!/bin/bash -e

install -vm 644 files/99-udisks2.rules "${ROOTFS_DIR}/etc/udev/rules.d/"
install -vm 440 files/50-udiskie.rules "${ROOTFS_DIR}/etc/polkit-1/rules.d/"
install -vm 440 files/10-poweroff-by-any-user.rules "${ROOTFS_DIR}/etc/polkit-1/rules.d/"
install -vm 644 files/mount_options.conf "${ROOTFS_DIR}/etc/udisks2/mount_options.conf"
install -vm 644 files/udiskie.service "${ROOTFS_DIR}/etc/systemd/system/"
install -vDm 755 files/resize_partitions.sh "${ROOTFS_DIR}/usr/local/lib/vintage-pi-tv-sys-mods/resize_partitions.sh"

sed -i 's|init=/usr/lib/raspberrypi-sys-mods/firstboot|init=/usr/local/lib/vintage-pi-tv-sys-mods/resize_partitions.sh|' "${ROOTFS_DIR}/boot/firmware/cmdline.txt"

on_chroot <<EOF
addgroup --system storage
adduser "${FIRST_USER_NAME}" storage

systemctl enable udiskie.service
EOF
