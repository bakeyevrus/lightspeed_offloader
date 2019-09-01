import paramiko
import logging
import os

log = logging.getLogger(__name__)


class SFTPClient:
    """
    Creates a SFTP client channel to host.

    :param host: (str) STFP server address
    :param port: (number) SFTP server port
    :param username: (str) username to connect to SFTP server
    :param password: (str) password for connection to SFTP server
    :param input_dir: (str) input folder located on SFTP server to fetch files from
    :param output_dir: (str) output folder located on SFTP server to place files into
    :param archive_dir: (str) archive folder located on SFTP server to place files into
    :param error_dir: (str) error folder located on SFTP server to place files into
    """

    def __init__(self, host, port, username, password, input_dir, output_dir, archive_dir, error_dir):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.archive_dir = archive_dir
        self.error_dir = error_dir
        self.sftp = self._init_client()

    def _init_client(self):
        log.info("Connecting to %s:%s as user %s", self.host, self.port, self.username)

        transport = paramiko.Transport((self.host, self.port))
        transport.connect(username=self.username, password=self.password)
        sftp = paramiko.SFTPClient.from_transport(transport)

        return sftp

    def list_input_files(self):
        """
        List all files from SFTP 'input_dir' directory, i.e from directory containing exported orders
        :return: an array of absolute paths to the files on SFTP server
        """
        return map(
            lambda file_name: os.path.join(self.input_dir, file_name),
            self.sftp.listdir(self.input_dir)
        )

    def get_file(self, path):
        """
        Gets file content for a given path on SFTP server. Note, that the file is NOT downloaded. The caller is
        responsible for closing the underlying stream.
        :param path: (str) absolute path to the file on SFTP server
        :return: content of the requested file
        """
        return self.sftp.open(path)

    def archive_file(self, path):
        """
        Moves a file into 'archive_dir'
        :param path: (str) absoulte path to the file on SFTP server
        """
        file_name = os.path.basename(path)
        target_dir = os.path.join(self.archive_dir, file_name)

        log.debug(f"Archiving file {path} to {target_dir}")
        self.sftp.rename(path, target_dir)

    def upload_error_file(self, error_orders_csv_path: str):
        """
        Uploads CSV file with error orders into the 'error_dir' folder on SFTP server
        :param error_orders_csv_path: (str) absolute path to the file with error orders
        """
        file_name = os.path.basename(error_orders_csv_path)
        target_dir = os.path.join(self.error_dir, file_name)

        log.debug(f"Uploading {error_orders_csv_path} into SFTP {target_dir}")
        self.sftp.put(error_orders_csv_path, target_dir)

    def upload_processed_orders(self, processed_orders_csv_path: str):
        """
        Uploads CSV file with processed orders into the 'output_dir' folder on SFTP server
        :param processed_orders_csv_path: (str) absolute path to the file with processed orders
        """
        file_name = os.path.basename(processed_orders_csv_path)
        target_dir = os.path.join(self.output_dir, file_name)

        log.debug(f"Uploading {processed_orders_csv_path} into SFTP {target_dir}")
        self.sftp.put(processed_orders_csv_path, target_dir)

    def __del__(self):
        self.sftp.close()
