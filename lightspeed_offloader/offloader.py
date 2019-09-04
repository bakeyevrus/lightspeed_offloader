import csv
import logging.config
import os
import shutil

import yaml

from shared import csv_writer
from shared.const.csv_column_names import ExportedOrderCSV, OrderConfirmationCSV
from shared.exceptions import ProcessOrderException, UnexpectedHTTPStatusCodeException

"""Folder name in which temporary files are stored"""
TMP_FOLDER = "tmp"
"""Email suffix used in the output CSV files."""
EMAIL_SUFFIX = "@westfalia.eu"

log = logging.getLogger(__name__)


def _process_files(sftp_client, lightspeed_client, lightspeed_shipment_id, lightspeed_shipment_value_id):
    """Fetches all the CSV files needed to be processed from SFTP server. Parses them, and
    generates orders via Lightspeed API. If the process finishes successfully, creates new CSV file with the
    status attribute and archives processed file.

    :param sftp_client: (SFTPClient) instance of the SFTPClient class
    :param lightspeed_client: (LightspeedClient) instance of the LightspeedClient class
    :param lightspeed_shipment_id: (str) ID needed to build shipment method ID
    :param lightspeed_shipment_value_id: (str) ID needed to build shipment method ID
    """
    files_to_process = sftp_client.list_input_files()

    if not files_to_process:
        log.warning("No new files detected")
        return

    orders_to_save = []
    for file_path in files_to_process:
        log.info(f"Processing file {file_path}")
        file = sftp_client.get_file(file_path)

        log.debug(f"Parsing file {file_path}")
        parsed_file = csv.DictReader(file, delimiter=';')

        processed_orders = _process_file(parsed_file,
                                         lightspeed_client,
                                         lightspeed_shipment_id,
                                         lightspeed_shipment_value_id
                                         )

        file.close()

        sftp_client.archive_file(file_path)
        orders_to_save.extend(processed_orders)

    if orders_to_save:
        processed_orders_csv = csv_writer.save_orders_as_csv(TMP_FOLDER, orders_to_save,
                                                             OrderConfirmationCSV.FIELDNAMES)
        sftp_client.upload_processed_orders(processed_orders_csv)
    else:
        log.warning("No orders have processed")


def _process_file(file, lightspeed_client, lightspeed_shipment_id, lightspeed_shipment_value_id):
    processed_orders = []

    for row in file:
        try:
            order_id = _process_row(row, lightspeed_client, lightspeed_shipment_id, lightspeed_shipment_value_id)
            log.info(f"Order with {order_id} has been successfully created for {row[ExportedOrderCSV.ORDER_ID]}")
            order = _create_order_confirmation(order_id, row)
            processed_orders.append(order)
        except (ProcessOrderException, UnexpectedHTTPStatusCodeException) as e:
            log.error(f"Error occurred while processing order {row[ExportedOrderCSV.ORDER_ID]}")
            log.error(str(e))

    return processed_orders


def _process_row(row, lightspeed_client, lightspeed_shipment_id, lightspeed_shipment_value_id):
    checkout = _generate_checkout(row)
    checkout_id = lightspeed_client.create_checkout(checkout)

    variant_id = _get_variant_id(row, lightspeed_client)

    product = _generate_product_for_checkout(row, variant_id)
    lightspeed_client.add_product_to_checkout(product, checkout_id)

    methods_info = _generate_shipment_and_payment_methods(lightspeed_shipment_id, lightspeed_shipment_value_id)
    checkout = lightspeed_client.add_shipment_and_payment_methods(methods_info, checkout_id)

    if not checkout["payment_method"]:
        err_message = (f"Failed to add payment method to checkout {checkout_id}\n"
                       f"Checkout: {checkout}")
        raise ProcessOrderException(err_message)

    if not checkout["shipment_method"]:
        err_message = (f"Failed to add shipment method to checkout {checkout_id}\n"
                       f"Checkout: {checkout}")
        raise ProcessOrderException(err_message)

    validation = lightspeed_client.validate_checkout(checkout_id)

    if not validation["validated"]:
        err_message = (f"Checkout {checkout_id} haven't passed validation\n"
                       f"Validation errors: {validation['errors']}\n"
                       f"Checkout: {checkout}")
        raise ProcessOrderException(err_message)

    order_id = lightspeed_client.finish_checkout(checkout_id)

    payment_status = _generate_payment_status()
    order = lightspeed_client.update_order_payment_status(order_id, payment_status)
    if order["paymentStatus"] != "paid":
        err_message = f"Failed to update payment status of order {order_id}"
        raise ProcessOrderException(err_message)

    return order_id


def _generate_checkout(row):
    """
    Creates Lightspeed checkout object from a given CSV file row. See https://developers.lightspeedhq.com/ecom/endpoints/checkout/#post-create-a-new-checkout
    :param row: (str) a single line from CSV file obtained from SFTP server
    :return: a checkout dictionary representation
    """

    def _generate_address(exported_order):
        return {
            "name": exported_order[ExportedOrderCSV.FIRST_NAME] + " " + exported_order[ExportedOrderCSV.LAST_NAME],
            "address1": exported_order[ExportedOrderCSV.ADDRESS_STREET] + " " + exported_order[
                ExportedOrderCSV.ADDRESS_HOUSE],
            "address2": exported_order[ExportedOrderCSV.COMPANY],
            "zipcode": exported_order[ExportedOrderCSV.ZIP],
            "city": exported_order[ExportedOrderCSV.CITY],
            "country": exported_order[ExportedOrderCSV.COUNTRY],
            # House number should be -1 as has been agreed with business
            "number": "-1"
        }

    customer = {
        "firstname": row[ExportedOrderCSV.FIRST_NAME],
        "lastname": row[ExportedOrderCSV.LAST_NAME],
        "email": row[ExportedOrderCSV.EMAIL] + EMAIL_SUFFIX,
        "phone": "0"
    }

    billing_address = _generate_address(row)
    shipping_address = _generate_address(row)

    order = {
        "customer": customer,
        "billing_address": billing_address,
        "shipping_address": shipping_address,
        # TODO: find out if notifications needed since emails are non-existing
        "notification": False
    }
    return order


def _get_variant_id(row, lightspeed_client):
    product_ean = row[ExportedOrderCSV.EAN]

    variants = lightspeed_client.get_all_product_variants()

    for variant in variants:
        if variant["ean"] == product_ean:
            return variant["id"]

    raise ProcessOrderException(f"Cannot find product variant with EAN {product_ean}")


def _generate_product_for_checkout(row, variant_id):
    product_quantity = row[ExportedOrderCSV.QUANTITY]
    product_price = row[ExportedOrderCSV.PRICE]
    country = row[ExportedOrderCSV.COUNTRY]

    product = {
        "variant_id": variant_id,
        "quantity": product_quantity
    }

    # Special business requirement for Netherlands
    if country == "NL" or country == "nl":
        product["special_price_incl"] = product_price
    else:
        product["special_price_excl"] = product_price

    return product


def _generate_shipment_and_payment_methods(lightspeed_shipment_id, lightspeed_shipment_value_id):
    shipment_method = {
        "id": f"core|{lightspeed_shipment_id}|{lightspeed_shipment_value_id}"
    }

    # Payment method should be external and have 0 price
    payment_method = {
        "id": "external",
        "title": "Customer choice",
        "price_incl": 0,
        "tax_rate": 0
    }

    return {
        "shipment_method": shipment_method,
        "payment_method": payment_method
    }


def _generate_payment_status():
    return {
        "order": {
            "paymentStatus": "paid"
        }
    }


def _create_order_confirmation(order_id, row):
    from collections import OrderedDict
    from shared.const.order_statuses import CONFIRMED

    order_dict = OrderedDict()
    order_dict[OrderConfirmationCSV.ORDER_ID] = order_id
    order_dict[OrderConfirmationCSV.POSITION_NUM] = row[ExportedOrderCSV.POSITION_NUM]
    order_dict[OrderConfirmationCSV.QUANTITY] = row[ExportedOrderCSV.QUANTITY]
    order_dict[OrderConfirmationCSV.STATUS] = CONFIRMED

    return order_dict


def run(config_path):
    """
    Runs the entire application

    :param config_path: (str) path to the application config file
    :return: exit code 0 if terminated successfully, 1 otherwise
    """

    from shared.config_parser import ConfigParser
    from paramiko.ssh_exception import SSHException
    # get values from the config file
    config_parser = None
    try:
        config_parser = ConfigParser(config_path)
    except yaml.YAMLError as e:
        log.critical("Load of config file %s failed. Check correctness of the config file.", config_path)
        return 1

    sftp_client = None
    try:
        sftp_client = config_parser.create_sftp_client()
    except SSHException as e:
        log.critical(f"Cannot connect to SFTP server. Error message: {e}")
        return 1

    lspeed_client = config_parser.create_lightspeed_client()
    if not lspeed_client:
        return 1

    config = config_parser.get_config()
    lspeed_shipment_id = config["lightspeed-shipment-id"]
    lspeed_shipment_value_id = config["lightspeed-shipment-value-id"]

    # Create temp folder
    log.debug(f"Creating temp '{TMP_FOLDER}' folder")
    os.makedirs(TMP_FOLDER, exist_ok=True)

    _process_files(sftp_client, lspeed_client, lspeed_shipment_id, lspeed_shipment_value_id)

    # # Test code
    # file = None
    # try:
    #     file = open("SAMPLE.csv", "r")
    #     parsed_file = csv.DictReader(file, delimiter=';')
    #
    #     processed_orders = _process_file(parsed_file, lspeed_client, lspeed_shipment_id,
    #                                      lspeed_shipment_value_id)
    # finally:
    #     if file:
    #         file.close()

    log.debug(f"Removing temp '{TMP_FOLDER}' folder")
    shutil.rmtree(TMP_FOLDER)
    return 0
