from functools import cache, wraps
import logging
import os
from pathlib import Path
import subprocess
import threading
import time

from uvicorn.logging import ColourizedFormatter


logger = logging.getLogger(__name__)


def init_logger():
    log_fmt = "{asctime} {levelprefix:<8} {message} [thread={threadName}]"
    vintage_pi_tv_logger = logging.getLogger(__name__).parent
    vintage_pi_tv_logger.setLevel(logging.INFO)

    loggers = {
        logging.getLogger("uvicorn"): f"{log_fmt} (uvicorn)",
        vintage_pi_tv_logger: f"{log_fmt} ({{name}})",
    }

    for logger, format in loggers.items():
        for handler in logger.handlers:
            logger.removeHandler(handler)
        handler = logging.StreamHandler()
        formatter = ColourizedFormatter(format, style="{")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logging.getLogger("watchfiles.main").setLevel(logging.ERROR)  # Silence watchfiles logs


def set_log_level(level):
    vintage_pi_tv_logger = logging.getLogger(__name__).parent
    vintage_pi_tv_logger.setLevel(level)


def listdir_recursive(dirname):
    return (os.path.join(dp, f) for dp, _, fn in os.walk(dirname) for f in fn)


def high_precision_sleep(duration):
    start_time = time.perf_counter()
    while True:
        elapsed_time = time.perf_counter() - start_time
        remaining_time = duration - elapsed_time
        if remaining_time <= 0:
            break
        if remaining_time > 0.02:  # Sleep for 5ms if remaining time is greater
            time.sleep(max(remaining_time / 2, 0.0001))  # Sleep for the remaining time or minimum sleep interval
        else:
            pass


class FPSClock:
    def __init__(self):
        self.last_tick = None

    def tick(self, fps: int = 60):
        if self.last_tick is not None:
            sleep_secs = (1.0 / fps) - (time.monotonic() - self.last_tick)
        else:
            sleep_secs = 1.0 / fps

        if sleep_secs > 0:
            time.sleep(sleep_secs)

        self.last_tick = time.monotonic()


@cache
def is_docker():
    return Path("/.dockerenv").exists()


@cache
def is_raspberry_pi():
    if not is_docker():
        file_to_check = "/sys/firmware/devicetree/base/model"
        if os.path.exists(file_to_check):
            try:
                with open(file_to_check, "rb") as file:
                    return b"raspberry pi" in file.read().lower()
            except OSError:
                pass
    return False


@cache
def get_vintage_pi_tv_version():
    code_dir = Path(__name__).resolve().absolute().parent
    version_file = code_dir / "version.txt"
    git_dir = code_dir / ".git"
    try:
        if version_file.exists():
            with open(version_file, "r") as f:
                return f.read().strip()
        elif git_dir.is_dir():
            return subprocess.check_output(("git", f"--git-dir={git_dir}", "rev-parse", "HEAD"), text=True).strip()[:8]
        else:
            logger.warning("Couldn't resolve version. No git repository or version.txt file.")
    except Exception:
        logger.exception("Error resolving version")
    return "unknown"


def retry_thread_wrapper(func):
    wraps(func)

    def wrapped(*args, **kwargs):
        thread_name = threading.current_thread().name
        while True:
            try:
                func(*args, **kwargs)
            except Exception:
                logger.exception(f"Thread {thread_name} threw an exception. Restarting soon.")
                time.sleep(0.25)
            else:
                logger.debug(f"Thread {thread_name} returned cleanly. Exiting.")
                break

    return wrapped
