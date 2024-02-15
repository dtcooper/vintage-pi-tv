import asyncio
import json
import logging
import os
import sys
import weakref

import janus
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from .constants import ENV_ARGS_VAR_NAME
from .tv import VintagePiTV


if sys.version_info < (3, 7):
    raise Exception("Python version 3.7 or greater needed!")  # For ordering of dicts


logger = logging.getLogger(__name__)


async def index(request):
    return PlainTextResponse("There are only forty people in the world and five of them are hamburgers.\n")


websockets: weakref.WeakSet[WebSocket] = weakref.WeakSet()


async def websocket_index(websocket: WebSocket):
    await websocket.accept()
    websockets.add(websocket)
    async for data in websocket.iter_json():
        print(data)


# __main__.py passes these arguments as environment variables
kwargs = {}
if env_args := os.environ.get(ENV_ARGS_VAR_NAME):
    try:
        kwargs.update(json.loads(env_args))
    except json.JSONDecodeError:
        logger.critical(f"Error decoding JSON from environment variable {ENV_ARGS_VAR_NAME}: {env_args}")


websocket_updates_queue: janus.Queue[dict] = janus.Queue()
tv = VintagePiTV(websocket_updates_queue=websocket_updates_queue.sync_q, **kwargs)
background_tasks = set()


async def websocket_publisher():
    while True:
        state = await websocket_updates_queue.async_q.get()
        for websocket in websockets:
            try:
                await websocket.send_json(state)
            except Exception:
                logger.exception("Error writing to websocket")
        websocket = None  # Remove reference, so weakset can recycle


async def startup():
    task = asyncio.create_task(websocket_publisher())
    background_tasks.add(task)


async def shutdown():
    for task in background_tasks:
        task.cancel()


app = Starlette(
    routes=[Route("/", index), WebSocketRoute("/", websocket_index)],
    debug=tv.config.log_level == "DEBUG",
    on_startup=[tv.startup, startup],
    on_shutdown=[tv.shutdown, shutdown],
)
