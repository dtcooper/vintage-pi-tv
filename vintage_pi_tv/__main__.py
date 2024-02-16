import argparse
import json
import os
from pathlib import Path
import sys

import uvicorn

from vintage_pi_tv.constants import DEFAULT_CONFIG_PATHS, DEFAULT_PORT, ENV_ARGS_VAR_NAME, ENV_RELOAD_PID_NAME
from vintage_pi_tv.utils import is_docker


def generate_videos_config(config_file: Path, extra_search_dirs):
    # Just enough to initialize the videos DB
    import logging

    import tomlkit

    from vintage_pi_tv.config import Config
    from vintage_pi_tv.utils import resolve_config_tries
    from vintage_pi_tv.videos import VideosDB

    # Shut up logger
    setattr(logging.getLoggerClass(), "trace", lambda *args, **kwargs: None)
    logging.disable(logging.CRITICAL)

    config_files = resolve_config_tries(config_file)
    config_file = config_files[0] if config_files else None

    config = Config(path=config_file, extra_search_dirs=extra_search_dirs, channel_mode="alphabetical")
    videos = VideosDB(config=config)

    toml = tomlkit.document()
    videos_toml = toml["video"] = tomlkit.aot()

    seen_filenames = set()
    for video in videos.videos:
        if video.filename not in seen_filenames and not video.from_config:
            videos_toml.append({
                "filename": video.filename,
                "name": video.name,
                "enabled": True,
                "rating": config.default_rating,
                "subtitles": False,
            })
            seen_filenames.add(video.filename)

    print("# Videos to add to configuration\n")
    print(tomlkit.dumps(toml))


def run(args=None):
    parser = argparse.ArgumentParser(description="Run Vintage Pi TV")
    config_group = parser.add_mutually_exclusive_group()
    if is_docker():
        config_help_str = "using Docker you must specify a configuration file explicitly"
    else:
        absolute_default_config_paths = map(lambda p: str(Path(p).absolute()), DEFAULT_CONFIG_PATHS)
        config_help_str = f"if empty will try these in order:' {', '.join(absolute_default_config_paths)}"
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
        "-l",
        "--log-level",
        help="Override log level",
        dest="log_level_override",
        choices=("critical", "error", "warning", "info", "debug", "trace"),
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Bind webserver to host [default: 0.0.0.0]", metavar="<ip-address>"
    )
    parser.add_argument(
        "--port",
        default=DEFAULT_PORT,
        help=f"Bind webserver to port [default: {DEFAULT_PORT}]",
        metavar="<port>",
        type=int,
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
    parser.add_argument(
        "--generate-videos-config", action="store_true", help="generate [[video]] for any discovered videos"
    )
    args = parser.parse_args(args)

    if is_docker() and not args.extra_search_dirs:
        args.extra_search_dirs.append("/app/videos")

    if args.generate_videos_config:
        generate_videos_config(config_file=args.config_file, extra_search_dirs=args.extra_search_dirs)
        sys.exit(0)

    if args.config_wait < 0:
        parser.error("--wait-for-config-seconds should greater than or equal to 0")

    # Since uvicorn needs to completely load program for --reload to work, most of these as environment variables
    env = {
        key: getattr(args, key)
        for key in vars(args).keys()
        if key not in ("reload", "host", "port", "generate_videos_config")
    }

    uvicorn_kwargs = {"host": args.host, "port": args.port}
    if args.reload:
        uvicorn_kwargs.update(
            {"reload": True, "reload_includes": ["*.py", "*.toml"], "reload_dirs": [Path(__file__).resolve().parent]}
        )
        os.environ[ENV_RELOAD_PID_NAME] = str(os.getpid())

    os.environ[ENV_ARGS_VAR_NAME] = json.dumps(env, sort_keys=True, separators=(",", ":"))
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    uvicorn.run("vintage_pi_tv.app:app", **uvicorn_kwargs)


if __name__ == "__main__":
    run()
