import logging
import yaml
from .password_encryption import decrypt

log = logging.getLogger(__name__)


class ConfigParser:
    def __init__(self, config_path):
        self._load_config(config_path)

    def _load_config(self, config_file):
        """
        Loads configuration file.
        :param config_file: (str) path to file containing configuration
        """
        with open(config_file, "rt") as f:
            self.config = yaml.safe_load(f.read())
            f.close()

    def create_sftp_client(self):
        """
        Creates sftp client based on the provided config
        :return: an instance of SFTPClient class
        """
        from .sftp_client import SFTPClient

        sftp_host = self.config["sftp-host"]
        sftp_port = self.config["sftp-port"]
        sftp_user = self.config["sftp-user"]
        sftp_pass_file = self.config["sftp-pass-path"]
        sftp_password = None
        try:
            sftp_password = decrypt(self.config["master-password"], sftp_pass_file)
        except IOError as e:
            log.critical(f"Cannot read {sftp_pass_file} file")
            return None

        sftp_input_dir = self.config["sftp-input-folder"]
        sftp_output_dir = self.config["sftp-output-folder"]
        sftp_archive_dir = self.config["sftp-archive-folder"]

        return SFTPClient(sftp_host, sftp_port, sftp_user, sftp_password, sftp_input_dir, sftp_output_dir,
                          sftp_archive_dir)

    def create_lightspeed_client(self):
        """
        Creates Lightspeed client based on the provided config
        :return: an instance of LightspeedClient class
        """
        from .lightspeed_client import LightspeedClient

        lspeed_api_url = self.config["lightspeed-api-url"]
        lspeed_api_key = self.config["lightspeed-api-key"]
        lspeed_api_secret_file = self.config["lightspeed-api-secret-path"]
        lspeed_api_secret = None
        try:
            lspeed_api_secret = decrypt(self.config["master-password"], lspeed_api_secret_file)
        except IOError as e:
            log.critical(f"Cannot read {lspeed_api_secret_file} file")
            return None

        return LightspeedClient(lspeed_api_url, lspeed_api_key, lspeed_api_secret)

    def get_config(self):
        """
        Returns parsed config
        :return: parsed config file as Python dictionary
        """
        return self.config
