from __future__ import annotations

import errno
import functools
import logging
import queue
import selectors
import subprocess
import tempfile
import time
from typing import TYPE_CHECKING

import tomlkit

from .constants import DEFAULT_IR_SCANCODES


if TYPE_CHECKING:
    from .config import Config


try:
    from evdev import InputDevice, ecodes, list_devices
    from evdev.ecodes import EV_KEY
    from evdev.events import KeyEvent
    import pyudev
except ImportError:
    KEYBOARD_AVAILABLE = False
else:
    KEYBOARD_AVAILABLE = True
    KEY_EVENT_DOWN = KeyEvent.key_down
    KEY_EVENT_HOLD = KeyEvent.key_hold
    KEY = ecodes.bytype[EV_KEY]


logger = logging.getLogger(__name__)


def is_valid_key(s):
    # Keyboard isn't avialable anyway, why throw an error?
    return s.startswith("KEY_") and (not KEYBOARD_AVAILABLE or s in dir(ecodes))


class Keyboard:
    def _enable_ir_remote(self):
        scancodes = tomlkit.table()

        for key in DEFAULT_IR_SCANCODES.keys():
            value = self.config.ir_remote[key]
            if not isinstance(value, bool):
                if keyboard_key := self.config.keyboard[key]:
                    item = tomlkit.item(keyboard_key)
                    item.comment(key)
                    scancodes.add(f"0x{value:02X}", item)
                else:
                    logger.warning(f"Can't enable {key} for IR remote, as there's no keyboard key assigned for it!")
            else:  # Will always be false if it's a bool
                scancodes.add(tomlkit.comment(f"{key} disabled by config"))

        if scancodes:
            toml = tomlkit.document()
            toml["protocols"] = tomlkit.aot()
            toml["protocols"].append(
                tomlkit.item({
                    "name": "Vintage Pi TV Remote",
                    "protocol": self.config.ir_remote["protocol"],
                    "variant": self.config.ir_remote["variant"],
                    "scancodes": scancodes,
                })
            )

            with tempfile.NamedTemporaryFile(prefix="vintage-pi-tv-", suffix=".toml", mode="w") as file:
                logger.debug(f"Writing ir-keytable config to {file.name}:\n{tomlkit.dumps(toml)}")
                tomlkit.dump(toml, file)
                file.flush()
                try:
                    response = subprocess.check_output(
                        ("sudo", "ir-keytable", "--clear", "--write", file.name), text=True, stderr=subprocess.STDOUT
                    )
                except subprocess.CalledProcessError:
                    logger.exception("Error calling ir-keytable with the following toml\n{tomlkit.dumps(toml)}")
                else:
                    logger.debug(f"Got following reponse from ir-keytable: {response}")
                logger.info("Enabled remote")

        else:
            logger.warning("No scancodes provided for IR remote. Disabling")
            self.config.ir_remote["enabled"] = False

    def keyboard_thread(self):
        # Listening for key events on Linux is a fucking mess.
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem="input")
        monitor.start()

        while True:
            try:
                devices = {name: InputDevice(name) for name in list_devices()}
                selector = selectors.DefaultSelector()
                for device in devices.values():
                    logger.debug(f"Listening for keyboard events on device {device.path}")
                    selector.register(device, selectors.EVENT_READ)
                selector.register(monitor, selectors.EVENT_READ)

                while True:
                    for device in map(lambda val: val[0].fileobj, selector.select()):
                        if device is monitor:
                            for udev in iter(functools.partial(monitor.poll, 0), None):
                                if not udev.device_node:
                                    break
                                if udev.action == "add":
                                    if udev.device_node not in devices:
                                        try:
                                            devices[udev.device_node] = InputDevice(udev.device_node)
                                        except IOError as e:
                                            if e.errno != errno.ENOTTY:
                                                raise
                                        else:
                                            selector.register(devices[udev.device_node], selectors.EVENT_READ)
                                            logger.debug(f"Listening for keyboard events on device {udev.device_node}")
                                elif udev.action == "remove":
                                    if udev.device_node in devices:
                                        logger.debug(
                                            "Stopped listening for keyboard events on device:"
                                            f" {udev.device_node} (udev)"
                                        )
                                        selector.unregister(devices[udev.device_node])
                                        del devices[udev.device_node]
                        else:
                            try:
                                for event in device.read():
                                    if event.type == EV_KEY:
                                        if event.value == KEY_EVENT_DOWN:
                                            self.queue.put(("KEYPRESS", "DOWN", KEY[event.code]))
                                        elif event.value == KEY_EVENT_HOLD:
                                            self.queue.put(("KEYPRESS", "HOLD", KEY[event.code]))
                            except OSError as e:
                                if e.errno != errno.ENODEV:
                                    raise
                                logger.debug(f"Stopped listening for keyboard events on device: {device.path} (read)")
                                selector.unregister(devices[device.path])
                                del devices[device.path]

            except Exception:
                logger.exception("Something went wrong while monitoring keyboard events. Trying again.")
                time.sleep(0.5)

    def __init__(self, queue: queue.Queue, config: Config):
        if not KEYBOARD_AVAILABLE:
            raise Exception("No keyboard is available on this platform! Should not have gotten here.")

        self.queue = queue
        self.config = config

        if self.config.ir_remote["enabled"]:
            self._enable_ir_remote()
        else:
            logger.info("IR remote disabled")
