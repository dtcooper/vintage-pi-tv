import datetime

from termcolor import colored


LOG_LEVELS = {"silent": 0, "error": 1, "warning": 2, "info": 3, "debug": 4}
_log_level = 3


def set_log_level(level):
    global _log_level
    _log_level = level


def log(level, s):
    if level <= _log_level:
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] {s}")


def error(s):
    log(1, colored(s, "red", attrs=["bold"]))
