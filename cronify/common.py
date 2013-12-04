"""Common components for cronify package. Configuration reading, event codes"""

import yaml
from pyinotify import EventsCodes

CFG_FILE = "/etc/cronify.yaml"
_MASKS = EventsCodes.ALL_FLAGS["IN_CLOSE_WRITE"] | EventsCodes.ALL_FLAGS["IN_MOVED_FROM"]

def read_cfg(cfg_fileh):
    """Read cfg file, return configuration as dictionary
    :rtype: dict
    :return: watch_data dictionary"""
    data = yaml.load(cfg_fileh)
    cfg_fileh.close()
    return data
