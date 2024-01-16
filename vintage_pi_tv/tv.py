import shutil
import sys

from . import constants, log


class VintagePiTV:
    def __init__(self, config=constants.CONFIG_DEFAULT, readonly_config=False):
        self.config = config
        self.readonly_config = readonly_config

        if not self.config.exists():
            if self.readonly_config:
                log.error(f"Config file {self.config} does not exist!")
                sys.exit(1)
            else:
                shutil.copy(constants.CONFIG_SAMPLE_PATH, self.config)
                log.warning(f"Copied default configuration to {self.config}")

        log.debug("debug")
        log.success("success")
        log.info("info")
        log.warning("warning")
        log.error("error")

    def run(self):
        print(f"{self.config=}")
        print(f"{self.readonly_config=}")
