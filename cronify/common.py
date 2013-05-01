import pyaml

CFG_FILE = "/etc/cronify.yaml"

def read_cfg():
    """Read cfg file, return configuration as dictionary
    :rtype: dict
    :return: watch_data dictionary"""
    with open(CFG_FILE, 'r') as cfg_fileh:
        return pyaml.yaml.load(cfg_fileh)
