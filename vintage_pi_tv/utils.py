import logging
import os
import time

from uvicorn.logging import ColourizedFormatter


def init_logger():
    log_fmt = "{asctime} {levelprefix:<8} {message}"

    loggers = {
        logging.getLogger("uvicorn"): f"{log_fmt} (uvicorn)",
        logging.getLogger(__name__).parent: f"{log_fmt} ({{name}})",
    }

    for logger, format in loggers.items():
        for handler in logger.handlers:
            logger.removeHandler(handler)
        handler = logging.StreamHandler()
        formatter = ColourizedFormatter(format, style="{")
        handler.setFormatter(formatter)
        logger.addHandler(handler)


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
