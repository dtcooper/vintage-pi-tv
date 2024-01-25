import argparse
import os
from pathlib import Path
import subprocess
import sys

import uvicorn

from vintage_pi_tv.constants import DEFAULT_CONFIG_PATHS


MPV_HELP_DRM_CONNECTER_LINE_PREFIX = "Available modes for drm-connector="
# MPV_HELP_MODE_LINE_PREFIX

def run(args=None):
    absolute_default_config_paths = map(lambda p: str(Path(p).absolute()), DEFAULT_CONFIG_PATHS)

    parser = argparse.ArgumentParser(description="Run Vintage Pi TV")
    parser.add_argument(
        "-c",
        "--config",
        dest="config_file",
        help=f"path to config file, if empty will try these in order: {', '.join(absolute_default_config_paths)}",
        metavar="config.toml",
    )
    parser.add_argument(
        "-w",
        "--wait-for-config-seconds",
        default=0,
        help=(
            "number of seconds (rounded to the nearest integer) to sleep for waiting for config to appear, useful if"
            " config lives on a to-be-mounted filesystem [default: 0]"
        ),
        metavar="<int>",
        type=int,
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Bind webserver to host [default: 0.0.0.0]", metavar="<ip-address>"
    )
    parser.add_argument(
        "--port", default=6672, help="Bind webserver to port [default: 6672]", metavar="<port>", type=int
    )
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args(args)

    if args.wait_for_config_seconds < 0:
        parser.error("--wait-for-config-seconds should greater than or equal to 0")

    # Since uvicorn needs to completely load program for --reload to work, pass these as environment variables
    if args.config_file is not None:
        os.environ["VINTAGE_PI_TV_CONFIG_FILE"] = args.config_file
    if args.wait_for_config_seconds > 0:
        os.environ["VINTAGE_PI_TV_WAIT_FOR_CONFIG_SECONDS"] = str(args.wait_for_config_seconds)

    kwargs = {"host": args.host, "port": args.port}
    if args.reload:
        os.environ["VINTAGE_PI_TV_UVICORN_RELOAD_PARENT_PID"] = str(os.getpid())
        kwargs.update({"reload": True, "reload_includes": ["*.py", "config.toml"]})

    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    uvicorn.run("vintage_pi_tv.app:app", **kwargs)


if __name__ == "__main__":
    run()
