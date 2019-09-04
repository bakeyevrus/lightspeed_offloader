import os
import logging
import logging.config
import sys
import yaml
from argparse import ArgumentParser
from . import checker


def _get_parser():
    """Gets parser object for this script

    :return: an instance of ArgumentParser
    """

    parser = ArgumentParser()
    parser.add_argument("-c", "--config",
                        dest="config",
                        help="path to configuration file",
                        type=lambda conf_path: _is_valid_file(parser, conf_path),
                        required=True)
    parser.add_argument("-l", "--log-config",
                        dest="log_config",
                        help="path to log configuration file",
                        type=lambda conf_path: _is_valid_file(parser, conf_path),
                        required=True)

    return parser


def _is_valid_file(parser: ArgumentParser, file: str):
    """Checks if file is valid, and exists on the local file system.

    :param parser: an instance of ArgumentParser
    :param file: file path to be checked for existence
    :return: path to file if this file exists on the local file system
    """

    file = os.path.abspath(file)
    if not os.path.exists(file):
        parser.error(f"The file {file} does not exists.")
    else:
        return file


def _setup_logging(path="./config/logging.yaml", default_level=logging.INFO):
    """Setups logging based on the provided configuration YAML file.

    :param path: (str) path to the log configuration file
    :param default_level: (int) logging level when no log configuration file is defined
    """

    if os.path.exists(path):
        with open(path, "rt") as f:
            log_config = yaml.safe_load(f.read())
        logging.config.dictConfig(log_config)
    else:
        logging.basicConfig(level=default_level)


# Parse script arguments
args = _get_parser().parse_args()

# Setup logging
log_config_path = args.log_config
_setup_logging(path=log_config_path)

# Run app
app_config_path = args.config
sys.exit(checker.run(app_config_path))
