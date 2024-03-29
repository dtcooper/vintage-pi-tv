import asyncio
import hmac
import json
import logging
import os
from pathlib import Path
import sys
from time import monotonic as tick
import weakref

import janus
from starlette.applications import Starlette
from starlette.routing import Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

from .constants import ENV_ARGS_VAR_NAME, PROTOCOL_VERSION
from .tv import VintagePiTV
from .utils import exit, get_vintage_pi_tv_version


if sys.version_info < (3, 7):
    raise Exception("Python version 3.7 or greater needed!")  # For ordering of dicts


logger = logging.getLogger(__name__)

REQUIRED_BROADCAST_DATA_KEYS_TO_START = ("state", "current_rating", "ratings", "videos_db", "version", "volume")
broadcast_data = {"version": get_vintage_pi_tv_version()}
websockets: weakref.WeakSet[WebSocket] = weakref.WeakSet()
websocket_updates_queue: janus.Queue[dict] = janus.Queue()
event_queue: janus.Queue[dict] = janus.Queue()


async def websocket_index(websocket: WebSocket):
    await websocket.accept()
    greeting = await websocket.receive_json()
    protocol_version, password = greeting.get("protocol_version"), greeting.get("password")

    if protocol_version is None or password is None:
        await websocket.close(4001, "Invalid handshake. Something went wrong.")

    elif protocol_version != PROTOCOL_VERSION:
        what, action = ("an older", "downgrade") if protocol_version > PROTOCOL_VERSION else ("a newer", "upgrade")
        await websocket.close(4001, f"Server running {what} protocol than you. You'll need to {action} Vintage Pi TV.")

    elif tv.config.web_password and not hmac.compare_digest(password, tv.config.web_password):
        await websocket.close(4000, "Invalid password. Try again.")

    else:
        await websocket.send_json(broadcast_data)  # Hello message
        websockets.add(websocket)
        async for data in websocket.iter_json():
            action = data.pop("action")
            await event_queue.async_q.put({"event": "user-action", "action": action, "extras": data})


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
            exit(1, "Couldn't initialize web app, required data not found!", force=True)


async def shutdown():
    for task in background_tasks:
        task.cancel()


routes = [
    WebSocketRoute("/ws", websocket_index),
    Mount("/", app=StaticFiles(directory=Path(__file__).parent.parent / "web" / "dist", html=True, check_dir=False)),
]


app = Starlette(
    routes=routes,
    debug=tv.config.log_level == "DEBUG",
    on_startup=[tv.startup, startup],
    on_shutdown=[tv.shutdown, shutdown],
)
