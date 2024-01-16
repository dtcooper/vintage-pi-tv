#!/bin/bash

SCRIPT_NAME='/usr/local/lib/vintage-pi-tv-sys-mods/resize_partitions.sh'
FIRST_BOOT_SCRIPT_NAME='/usr/lib/raspberrypi-sys-mods/firstboot'
CONFIG_SRC=vintage-pi-tv-config.toml
CONFIG_DEST=config.toml
ROOT_DEV_MAX_PARTSIZE="$((1024 * 1024 * 512 * 15))"  # 7.5GiB
EXFAT_PARTITION_LABEL='Vintage Pi TV'

reboot_pi() {
    umount "$FWLOC"
    mount / -o remount,ro
    sync
    reboot -f "$BOOT_PART_NUM"
    sleep 5
    exit 0
}

error() {
    echo "ERROR: $1"
    whiptail --infobox "ERROR: $1" 20 60
    sleep 5
    reboot_pi
}

__PARTED_DATA=
parted_data() {
    # parted_data <line> <column> <strip_bytes>
    local OUTPUT

    if [ -z "${__PARTED_DATA}" ]; then
        __PARTED_DATA="$(parted -m "${ROOT_DEV}" 'unit B print free' | sed 's/;$//g')"
    fi

    OUTPUT="${__PARTED_DATA}"
    if [ "$1" ]; then
        OUTPUT="$(echo "${OUTPUT}" | sed -n "${1}p")"
    fi
    if [ "$2" ]; then
        OUTPUT="$(echo "${OUTPUT}" | cut -d ':' -f "${2}")"
    fi
    if [ "$3" ]; then
        OUTPUT="$(echo "${OUTPUT}" | sed 's/B$//')"
    fi
    echo "${OUTPUT}"
}

main() {
    [ "${ROOT_DEV_NAME}" = "${BOOT_DEV_NAME}" ] || error 'Root device was expected to be the same as boot device'
    [ ! -e "${EXFAT_PART_DEV}" ] || error 'Third partition already exists'
    [ "${ROOT_DEV_FSTYPE}" = 'ext4' ] || error 'Root device was expected to be ext4'
    [ "${BOOT_DEV_FSTYPE}" = 'vfat' ] || error 'Boot device was expected to be vfat'

    [ "$(parted_data 1)" = 'BYT' ] || error 'Unexpected partition data'
    [ "$(parted_data 2 2 true)" = "${DEV_SIZE}" ] || error 'Unexpected device size'
    [ "$(parted_data 2 6)" = 'msdos' ] || error 'Unexpected partition table type'
    [ "$(parted_data 3 5)" = 'free' ] || error 'Expected empty space before first partition'
    [ "$(parted_data 4 1)" = '1' -a "$(parted_data 4 5)" = 'fat32' ] || error 'Expected fat32 first partition'
    [ "$(parted_data 5 1)" = '2' -a "$(parted_data 5 5)" = 'ext4' ] || error 'Expected ext4 second partition'
    [ "$(parted_data 6 5)" = 'free' ] || error 'Expected empty space after second partition'
    [ -z "$(parted_data 7)" ] || error 'More partition data than expected!'

    ROOT_DEV_START="$(parted_data 5 2 true)"
    ROOT_DEV_END="$((ROOT_DEV_START + ROOT_DEV_MAX_PARTSIZE - 1))"
    ROOT_DEV_END="$((ROOT_DEV_END > DEV_SIZE ? DEV_SIZE : ROOT_DEV_END))"
    CURRENT_ROOT_DEV_END="$(parted_data 5 3 true)"
    if [ "${CURRENT_ROOT_DEV_END}" -ge "${ROOT_DEV_END}" ]; then
        echo "WARNING: ${ROOT_DEV} already ends on or after ${ROOT_DEV_END} (currently ${CURRENT_ROOT_DEV_END})!"
        ROOT_DEV_END="${CURRENT_ROOT_DEV_END}"
    else
        parted "${ROOT_DEV}" ---pretend-input-tty <<EOF
resizepart
2
Yes
${ROOT_DEV_END}B
quit
EOF
        partprobe
        resize2fs -f -p "${ROOT_PART_DEV}"
    fi

    EXFAT_DEV_START="$((ROOT_DEV_END + 1))"
    EXFAT_DEV_END=$((DEV_SIZE - 1))
    if [ "${EXFAT_DEV_START}" -ge "${DEV_SIZE}" ]; then
        echo "WARNING: ${ROOT_DEV} doesn't have enough space on it for an exFAT partition."
    else
        # TODO resize to the byte, not 100%
        parted -s "${ROOT_DEV}" "unit B mkpart primary ntfs ${EXFAT_DEV_START}B ${EXFAT_DEV_END}B"
        partprobe
        mkfs.exfat -L "${EXFAT_PARTITION_LABEL}" "${EXFAT_PART_DEV}"
        partprobe
        sync
        mount "${EXFAT_PART_DEV}" /mnt
        sync
        mkdir -v /mnt/videos
        ffmpeg -y \
            -f lavfi -i smptebars=duration=30:size=1280x720:rate=30 \
            -f lavfi -i "sine=frequency=1000:sample_rate=48000:duration=30" \
            /mnt/videos/colorbars.mkv
        mount "$FWLOC" -o remount,rw
        sync
        mv -v "${FWLOC}/${CONFIG_SRC}" "/mnt/${CONFIG_DEST}"
        mount "$FWLOC" -o remount,ro
        sync
        umount /mnt
        sync
    fi
}

if ! FWLOC=$(/usr/lib/raspberrypi-sys-mods/get_fw_loc); then
    whiptail --msgbox "Could not determine firmware partition" 20 60
    poweroff -f
fi

# Setup basic mountpoints
mountpoint -q /proc || mount -t proc proc /proc
mountpoint -q /sys || mount -t sysfs sys /sys
mountpoint -q /run || mount -t tmpfs tmp /run
mkdir -p /run/systemd

mount / -o remount,ro
mount "$FWLOC" -o rw
sync

# Compute variables
ROOT_PART_DEV="$(findmnt / -no source)"
ROOT_DEV_NAME="$(lsblk -no pkname "$ROOT_PART_DEV")"
ROOT_DEV="/dev/${ROOT_DEV_NAME}"
ROOT_DEV_FSTYPE="$(lsblk -no FSTYPE "$ROOT_PART_DEV")"

BOOT_PART_DEV="$(findmnt "$FWLOC" -no source)"
BOOT_PART_NAME="$(lsblk -no kname "$BOOT_PART_DEV")"
BOOT_DEV_NAME="$(lsblk -no pkname "$BOOT_PART_DEV")"
BOOT_DEV_FSTYPE="$(lsblk -no FSTYPE "$BOOT_PART_DEV")"
BOOT_PART_NUM="$(cat "/sys/block/${BOOT_DEV_NAME}/${BOOT_PART_NAME}/partition")"

DEV_SIZE="$(lsblk -ndb -o SIZE "${ROOT_DEV}")"

# May need a "p" if it ends in a number
EXFAT_PART_DEV="${ROOT_DEV}$(echo "${ROOT_DEV_NAME}" | grep -q '[0-9]$' && echo 'p')3"


# Remove single use script from init
sed -i "s| init=${SCRIPT_NAME}| init=${FIRST_BOOT_SCRIPT_NAME}|" "$FWLOC/cmdline.txt"

mount "$FWLOC" -o remount,ro
sync

main

whiptail --infobox "Rebooting in 5 seconds..." 20 60
sleep 5

reboot_pi
