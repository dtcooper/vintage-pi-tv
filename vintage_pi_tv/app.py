import asyncio
import hmac
import json
import logging
import os
import sys
from time import monotonic as tick
import weakref

import janus
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from .constants import ENV_ARGS_VAR_NAME
from .tv import VintagePiTV
from .utils import exit


if sys.version_info < (3, 7):
    raise Exception("Python version 3.7 or greater needed!")  # For ordering of dicts


logger = logging.getLogger(__name__)

REQUIRED_BROADCAST_DATA_KEYS_TO_START = ("state", "current_rating", "ratings")
broadcast_data = {}
websockets: weakref.WeakSet[WebSocket] = weakref.WeakSet()
websocket_updates_queue: janus.Queue[dict] = janus.Queue()
event_queue: janus.Queue[dict] = janus.Queue()


async def index(request):
    return PlainTextResponse("There are only forty people in the world and five of them are hamburgers.\n")


async def websocket_index(websocket: WebSocket):
    await websocket.accept()
    if tv.config.web_password:
        password = await websocket.receive_text()
        if hmac.compare_digest(password, tv.config.web_password):
            await websocket.send_text("success")
        else:
            await websocket.send_text("failed")
            await websocket.close()
            return

    await websocket.send_json(broadcast_data)
    websockets.add(websocket)
    async for data in websocket.iter_json():
        await event_queue.async_q.put(data)


# __main__.py passes these arguments as environment variables
kwargs = {}
if env_args := os.environ.get(ENV_ARGS_VAR_NAME):
    try:
        kwargs.update(json.loads(env_args))
    except json.JSONDecodeError:
        logger.critical(f"Error decoding JSON from environment variable {ENV_ARGS_VAR_NAME}: {env_args}")


tv = VintagePiTV(websocket_updates_queue=websocket_updates_queue.sync_q, event_queue=event_queue.sync_q, **kwargs)
background_tasks = set()


async def websocket_publisher():
    while True:
        data = await websocket_updates_queue.async_q.get()
        broadcast_data[data["type"]] = data["data"]
        for websocket in websockets:
            try:
                await websocket.send_json({data["type"]: data["data"]})
            except Exception:
                logger.exception("Error writing to websocket")
        websocket = None  # Remove reference, so weakset can recycle


async def startup():
    task = asyncio.create_task(websocket_publisher())
    background_tasks.add(task)

    error_after = tick() + 15.0  # Wait to startup for 15 seconds, then bail with error

    while True:
        if all(key in broadcast_data for key in REQUIRED_BROADCAST_DATA_KEYS_TO_START):
            logger.info("Web app got required data to start. Starting...")
            break
        await asyncio.sleep(0.05)

        if tick() > error_after:
            logger.critical("Couldn't initialize web app, required data not found.")
            exit(1)


async def shutdown():
    for task in background_tasks:
        task.cancel()


app = Starlette(
    routes=[Route("/", index), WebSocketRoute("/", websocket_index)],
    debug=tv.config.log_level == "DEBUG",
    on_startup=[tv.startup, startup],
    on_shutdown=[tv.shutdown, shutdown],
)
