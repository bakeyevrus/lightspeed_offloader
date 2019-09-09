import logging
import csv
import os
import re
import shutil

from shared import csv_writer
from shared.exceptions import UnexpectedHTTPStatusCodeException
from shared.sftp_client import SFTPClient
from shared.lightspeed_client import LightspeedClient
from shared.const.csv_column_names import OrderConfirmationCSV
from shared.const import order_statuses
from shared.const import FILE_TIMESTAMP_PATTERN

"""Folder name in which temporary files are stored"""
TMP_FOLDER = "tmp"

"""Number of days after which the file can be archived"""
FILE_ARCHIVE_PERIOD = 4

log = logging.getLogger(__name__)


def _process_all_files(sftp_client: SFTPClient, lspeed_client: LightspeedClient):
    files_to_process = sftp_client.list_output_files()

    if not files_to_process:
        log.warning("No files to process.")
        return

    orders_map = {}
    for file_path in files_to_process:
        log.info(f"Processing file {file_path}")
        file = sftp_client.get_file(file_path)

        all_orders_shipped = _process_file(file, orders_map)

        file.close()

        file_name = os.path.basename(file_path)
        if all_orders_shipped and _is_file_older_than(file_name, FILE_ARCHIVE_PERIOD):
            log.info(f"Archiving file {file_name}.")
            sftp_client.archive_file(file_path)

    shipped_orders = _process_all_confirmed_orders(orders_map, lspeed_client)

    if shipped_orders:
        log.debug(f"Saving {len(shipped_orders)} shipped orders into a CSV file.")
        csv_path = csv_writer.save_orders_as_csv(TMP_FOLDER, shipped_orders, OrderConfirmationCSV.FIELDNAMES)
        sftp_client.upload_processed_orders(csv_path)
    else:
        log.info("No new shipped order has been detected.")


def _process_file(file, orders_map: dict):
    file_reader = csv.DictReader(file, delimiter=";")

    all_orders_shipped = True
    for row in file_reader:
        order_id = row[OrderConfirmationCSV.ORDER_ID]
        order_status = row[OrderConfirmationCSV.STATUS]

        if order_status == order_statuses.SHIPPED:
            orders_map[order_id] = False
        elif order_status == order_statuses.CONFIRMED and order_id not in orders_map:
            orders_map[order_id] = row
            all_orders_shipped = False

    return all_orders_shipped


def _is_file_older_than(file_name: str, days: int = 4):
    """
    Checks if the file is older then the predefined number of days by parsing the timestamp in the name.
    :param file_name: name of the file to check
    :param days: number of days to compare against
    :return: boolean value
    """
    from datetime import datetime, timedelta

    try:
        match_obj = re.match(r"(PO|S)-([0-9-]*)", file_name)
        file_timestamp = match_obj.group(2)
        timestamp = datetime.strptime(file_timestamp, FILE_TIMESTAMP_PATTERN)
    except (ValueError, AttributeError) as e:
        log.error(f"Cannot determine creation date for file {file_name}.\nError: {e}")
    else:
        return timestamp < datetime.now() - timedelta(days=days)

    return False


def _process_all_confirmed_orders(orders_map: dict, lspeed_client: LightspeedClient):
    shipped_orders = []
    for order_id in orders_map:
        order_details = orders_map[order_id]
        if not order_details:
            continue

        log.debug(f"Processing order {order_id}.")

        order_shipped = _is_order_shipped(order_details, lspeed_client)

        if order_shipped:
            log.debug(f"Order {order_id} changed status to {order_statuses.SHIPPED}.")
            tracking_code = _get_tracking_code(order_id, lspeed_client)
            shipped_order = _create_shipped_order(order_details, tracking_code)
            shipped_orders.append(shipped_order)

    return shipped_orders


def _is_order_shipped(order_details, lspeed_client: LightspeedClient):
    order_id = order_details[OrderConfirmationCSV.ORDER_ID]
    try:
        actual_order_status = lspeed_client.get_order_status(order_id)
        return actual_order_status == "completed_shipped"
    except UnexpectedHTTPStatusCodeException as e:
        log.error(f"Failed to check order {order_id} status.\nError: {str(e)}")

    return False


def _get_tracking_code(order_id, lspeed_client: LightspeedClient):
    try:
        shipments = lspeed_client.get_shipment_for_order(order_id)

        if shipments:
            shipment = shipments[0]
            if shipment["status"] == "shipped":
                return shipment["trackingCode"]
    except UnexpectedHTTPStatusCodeException as e:
        log.error(f"Failed to get tracking code for order {order_id}.\nError: {str(e)}")

    return None


def _create_shipped_order(order_details: dict, tracking_code, shipment_carrier="GLS"):
    order = order_details.copy()
    order[OrderConfirmationCSV.STATUS] = order_statuses.SHIPPED
    order[OrderConfirmationCSV.TRACKING_NUMBER] = tracking_code
    order[OrderConfirmationCSV.SHIPMENT_CARRIER] = shipment_carrier

    return order


def run(config_path: str):
    """
    Runs status checker module. It starts with iterating over all order status CSV files, and building a hash map with
    orders needs to be checked. After every order status has been checked, new file with the newly shipped orders is
    created.
    :param config_path: path to the configuration YAML file
    :return: status code 0 if terminated successfully, otherwise 1
    """
    from yaml import YAMLError
    from paramiko.ssh_exception import SSHException
    from shared.config_parser import ConfigParser

    try:
        config_parser = ConfigParser(config_path)
    except YAMLError:
        log.critical(f"Failed to load config file {config_path}. Check the correctness of the config.")
        return 1

    try:
        sftp_client = config_parser.create_sftp_client()
    except SSHException as e:
        log.critical(f"Cannot connect to SFTP server. Error message: {e}")
        return 1

    lspeed_client = config_parser.create_lightspeed_client()
    if not lspeed_client or not sftp_client:
        return 1

    # Create temp folder
    log.debug(f"Creating temp '{TMP_FOLDER}' folder")
    os.makedirs(TMP_FOLDER, exist_ok=True)

    _process_all_files(sftp_client, lspeed_client)

    log.debug(f"Removing temp '{TMP_FOLDER}' folder")
    shutil.rmtree(TMP_FOLDER)

    return 0
