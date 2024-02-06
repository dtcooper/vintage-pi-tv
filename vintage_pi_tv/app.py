import json
import logging
import os
import sys

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from .constants import ENV_ARGS_VAR_NAME
from .tv import VintagePiTV


if sys.version_info < (3, 7):
    raise Exception("Python version 3.7 or greater needed!")  # For ordering of dicts


logger = logging.getLogger(__name__)


async def index(request):
    return PlainTextResponse("There are only forty people in the world and five of them are hamburgers.\n")


routes = [Route("/", index)]

# __main__.py passes these arguments as environment variables
kwargs = {}
if env_args := os.environ.get(ENV_ARGS_VAR_NAME):
    try:
        kwargs.update(json.loads(env_args))
    except json.JSONDecodeError:
        logger.critical(f"Error decoding JSON from environment variable {ENV_ARGS_VAR_NAME}: {env_args}")

tv = VintagePiTV(**kwargs)

app = Starlette(
    routes=routes,
    debug=tv.config.log_level == "DEBUG",
    on_startup=[tv.startup],
    on_shutdown=[tv.shutdown],
)
