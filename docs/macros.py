from pathlib import Path
import sys
from unittest.mock import Mock

from schema import Optional


def get_config_values():
    sys.path.append(str(Path(__file__).parent.parent))
    sys.modules.update({
        # These can be safely mocked out
        "vintage_pi_tv.keyboard": Mock(),
        "vintage_pi_tv.utils": Mock(is_docker=lambda: False, is_raspberry_pi=lambda: True),
    })

    from vintage_pi_tv.schemas import config_schema

    return tuple(
        # Name, Description, Optional (bool)
        (s.name or s.key, s.description, isinstance(s, Optional))
        for s in config_schema.schema.keys()
    )


def define_env(env):
    env.variables["CONFIG_VALUES"] = get_config_values()
