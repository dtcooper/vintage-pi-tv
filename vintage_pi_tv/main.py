import argparse
from pathlib import Path

from vintage_pi_tv import constants
from vintage_pi_tv.tv import VintagePiTV


def run(args=None):
    parser = argparse.ArgumentParser(description="Run Vintage Pi TV")
    parser.add_argument(
        "-c",
        "--config",
        help=f"config file (default: {constants.CONFIG_DEFAULT})",
        default=constants.CONFIG_DEFAULT,
        metavar="/path.to/config.toml",
        type=Path,
    )
    parser.add_argument("--readonly-config", action="store_true", help="run in readonly config mode")
    kwargs = vars(parser.parse_args())

    tv = VintagePiTV(**kwargs)
    tv.run()


if __name__ == "__main__":
    run()
