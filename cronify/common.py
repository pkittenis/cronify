import yaml

CFG_FILE = "/etc/cronify.yaml"

def read_cfg(cfg_fileh):
    """Read cfg file, return configuration as dictionary
    :rtype: dict
    :return: watch_data dictionary"""
    data = yaml.load(cfg_fileh)
    cfg_fileh.close()
    return data
