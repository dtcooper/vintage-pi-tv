import os

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from .tv import VintagePiTV


async def index(request):
    return PlainTextResponse("There are only forty people in the world and five of them are hamburgers.\n")


async def startup():
    print("Startup")


async def shutdown():
    print("Shutdown")


routes = [Route("/", index)]

# __main__.py passes these arguments as environment variables
tv = VintagePiTV(
    config_file=os.environ.get("VINTAGE_PI_TV_CONFIG_FILE") or None,
    wait_for_config_seconds=int(os.environ.get("VINTAGE_PI_TV_WAIT_FOR_CONFIG_SECONDS") or 0),
)

app = Starlette(
    routes=routes,
    debug=tv.config.log_level == "DEBUG",
    on_startup=[tv.startup],
    on_shutdown=[tv.shutdown],
)
