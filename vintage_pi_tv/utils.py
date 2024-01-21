import logging
import os

from uvicorn.logging import ColourizedFormatter


def init_logger():
    uvicorn_logger = logging.getLogger("uvicorn")
    vintage_pi_tv_logger = logging.getLogger(__name__).parent
    formats = {
        vintage_pi_tv_logger: "{asctime} {levelprefix:<8} {message} ({name})",
        uvicorn_logger: "{asctime} {levelprefix:<8} {message} (uvicorn)",
    }

    for logger_to_modify in (uvicorn_logger, vintage_pi_tv_logger):
        for handler in logger_to_modify.handlers:
            logger_to_modify.removeHandler(handler)
        handler = logging.StreamHandler()
        formatter = ColourizedFormatter(formats[logger_to_modify], style="{")
        handler.setFormatter(formatter)
        logger_to_modify.addHandler(handler)


def set_log_level(level):
    vintage_pi_tv_logger = logging.getLogger(__name__).parent
    vintage_pi_tv_logger.setLevel(level)


def listdir_recursive(dirname):
    return (os.path.join(dp, f) for dp, _, fn in os.walk(dirname) for f in fn)
