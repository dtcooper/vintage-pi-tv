import argparse
import json
import os
from pathlib import Path

import uvicorn

from vintage_pi_tv.constants import DEFAULT_CONFIG_PATHS, ENV_ARGS_VAR_NAME
from vintage_pi_tv.utils import is_docker


def run(args=None):
    parser = argparse.ArgumentParser(description="Run Vintage Pi TV")
    config_group = parser.add_mutually_exclusive_group()
    if is_docker():
        absolute_default_config_paths = map(lambda p: str(Path(p).absolute()), DEFAULT_CONFIG_PATHS)
        config_help_str = f"if empty will try these in order:' {', '.join(absolute_default_config_paths)}"
    else:
        config_help_str = "using Docker you must specify a configuration file explicitly"
    config_group.add_argument("-c", "--config", dest="config_file", help=config_help_str, metavar="config.toml")
    parser.add_argument(
        "-w",
        "--wait-for-config-seconds",
        dest="config_wait",
        default=0,
        help=(
            "number of seconds (rounded to the nearest integer) to sleep for waiting for config to appear, useful if"
            " config lives on a yet-to-be-mounted filesystem [default: 0]"
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
    parser.add_argument("-r", "--reload", action="store_true", help="Enable auto-reload when Python files change")
    parser.add_argument(
        "extra_search_dirs",
        nargs="*",
        metavar="<search-dir>",
        help=(
            "Adds an extra `search_dirs` entry to look for videos"
            f"{' (in Docker container /videos is added if none are specified)' if is_docker else ''}"
        ),
    )
    args = parser.parse_args(args)

    if args.config_wait < 0:
        parser.error("--wait-for-config-seconds should greater than or equal to 0")

    if is_docker() and not args.extra_search_dirs:
        args.extra_search_dirs.append("/app/videos")

    # Since uvicorn needs to completely load program for --reload to work, most of these as environment variables
    env = {key: getattr(args, key) for key in vars(args).keys() if key not in ("reload", "host", "port")}
    env["uvicorn_reload_parent_pid"] = None

    kwargs = {"host": args.host, "port": args.port}
    if args.reload:
        env["uvicorn_reload_parent_pid"] = os.getpid()
        kwargs.update({"reload": True})

    os.environ[ENV_ARGS_VAR_NAME] = json.dumps(env, sort_keys=True, separators=(",", ":"))
    uvicorn.run("vintage_pi_tv.app:app", **kwargs)


if __name__ == "__main__":
    run()
