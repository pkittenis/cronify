import pyaml

CFG_FILE = "/etc/cronify.yaml"

def read_cfg():
    """Read cfg file, return configuration as dictionary
    :rtype: dict
    :return: watch_data dictionary"""
    cfg_fileh = open(CFG_FILE, 'r')
    data = pyaml.yaml.load(cfg_fileh)
    cfg_fileh.close()
    return data
