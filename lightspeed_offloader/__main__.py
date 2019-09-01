import argparse
import os
import logging
import logging.config
import sys

import yaml
from . import offloader


def get_parser():
    """Gets parser object for this script

    Returns:
        Instance of ArgumentParser
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config",
                        dest="config",
                        help="path to configuration file",
                        type=lambda conf_path: is_valid_file(parser, conf_path),
                        required=True)
    parser.add_argument("-l", "--log-config",
                        dest="log_config",
                        help="path to log configuration file",
                        type=lambda conf_path: is_valid_file(parser, conf_path),
                        required=True)

    return parser


def is_valid_file(parser, arg):
    """Checks if arg is valid file that exists on the local file system.

    Parameters:
        parser (ArgumentParser) - ArgumentParser instance
        arg (str) - file path to be checked for existence

    Returns:
        Path to file if this file exists on the local file system
    """

    arg = os.path.abspath(arg)
    if not os.path.exists(arg):
        parser.error("The file %s does not exists." % arg)
    else:
        return arg


def setup_logging(path="./config/logging.yaml", default_level=logging.INFO):
    """Setups logging based on the provided configuration YAML file.

    Parameters:
        path (str) - path to log configuration file
        default_level (int) - logging level when no log configuration file is defined
    """

    if os.path.exists(path):
        with open(path, "rt") as f:
            log_config = yaml.safe_load(f.read())
        logging.config.dictConfig(log_config)
    else:
        logging.basicConfig(level=default_level)


# Parse script arguments
args = get_parser().parse_args()

# Setup logging
log_config_path = args.log_config
setup_logging(path=log_config_path)

# Run app
app_config_path = args.config
sys.exit(offloader.run(app_config_path))
