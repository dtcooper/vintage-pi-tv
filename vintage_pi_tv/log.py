import datetime

from termcolor import colored


LOG_LEVELS = {"silent": 0, "error": 1, "warning": 2, "info": 3, "debug": 4}
_log_level = 3


def set_log_level(level="info"):
    global _log_level
    _log_level = LOG_LEVELS[level]


def _log(level, s):
    if level <= _log_level:
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] {s}")


def error(s):
    _log(1, colored(s, "red", attrs=["bold"]))


def warning(s):
    _log(2, colored(s, "yellow", attrs=["bold"]))


def info(s):
    _log(3, s)


def success(s):
    _log(3, colored(s, "green"))


def debug(s):
    _log(4, colored(s, "grey"))
