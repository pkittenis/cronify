# This file is part of cronify

# Copyright (C) 2016 Panos Kittenis

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, version 2.1.

# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

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
