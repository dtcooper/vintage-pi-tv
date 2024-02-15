from functools import cache, wraps
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from uvicorn.logging import TRACE_LOG_LEVEL as TRACE, ColourizedFormatter

from .constants import ENV_RELOAD_PID_NAME


logger = logging.getLogger(__name__)


def init_logger():
    def trace(self, message, *args, **kwargs):
        if self.isEnabledFor(TRACE):
            self._log(TRACE, message, args, **kwargs)

    def root_trace(message, *args, **kwargs):
        logging.log(TRACE, message, *args, **kwargs)

    logging.addLevelName(TRACE, "TRACE")
    setattr(logging, "TRACE", TRACE)
    setattr(logging.getLoggerClass(), "trace", trace)
    setattr(logging, "trace", root_trace)

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


def format_seconds(secs):
    secs = round(secs or 0.0)
    hours = secs // 3600
    minutes = (secs // 60) % 60
    seconds = secs % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


class FPSClock:
    def __init__(self):
        self.last_tick = None

    def tick(self, fps: int = 60) -> None:
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
    code_dir = Path(__name__).resolve().parent
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


def retry_thread_wrapper(func, exc_cleanup_func=None):
    wraps(func)

    def wrapped(*args, **kwargs):
        thread_name = threading.current_thread().name
        logger.debug(f"Thread {thread_name} spawned")
        while True:
            try:
                func(*args, **kwargs)
            except Exception:
                logger.exception(f"Thread {thread_name} threw an exception. Restarting soon.")
                time.sleep(0.125)
                if exc_cleanup_func is not None:
                    logger.debug(f"Calling exception cleanup for thread {thread_name}")
                    exc_cleanup_func()
                time.sleep(0.125)
            else:
                logger.warning(f"Thread {thread_name} returned cleanly. Not restarting.")
                break

    return wrapped


def exit(status: int = 0, reason: str = "unspecified"):
    logger.critical(f"Exiting with status code: {status} (Reason: {reason})")
    reload_pid = os.environ.get(ENV_RELOAD_PID_NAME)
    if reload_pid is not None and reload_pid.isdigit():
        logger.debug(f"Sending SIGINT to uvicorn reload PID {reload_pid} ")
        os.kill(int(reload_pid), signal.SIGINT)
    if threading.current_thread() != threading.main_thread():
        logger.debug("Exiting from non-main thread")
        os._exit(status)
    else:
        logger.debug("Exiting from main thread")
        sys.exit(status)
