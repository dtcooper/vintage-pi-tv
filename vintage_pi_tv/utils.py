import logging
import os

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
