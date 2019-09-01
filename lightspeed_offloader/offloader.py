import csv
import logging.config
import os
import yaml
from datetime import datetime
from shared.process_order_exception import ProcessOrderException

TMP_FOLDER = "tmp"
CSV_DIALECT = "dial"
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

    first_iter = True
    for file_path in files_to_process:
        if not first_iter:
            break
        first_iter = False

        log.info(f"Processing file {file_path}")
        file = sftp_client.get_file(file_path)

        log.debug(f"Parsing file {file_path}")
        parsed_file = csv.DictReader(file, delimiter=';')

        (processed_orders, skipped_orders) = _process_file(parsed_file,
                                                           lightspeed_client,
                                                           lightspeed_shipment_id,
                                                           lightspeed_shipment_value_id
                                                           )

        file.close()

        sftp_client.archive_file(file_path)

        if processed_orders:
            processed_orders_csv = _create_processed_orders_csv(processed_orders)
            sftp_client.upload_processed_orders(processed_orders_csv)

        if skipped_orders:
            error_orders_csv = _create_error_orders_csv(skipped_orders, parsed_file.fieldnames)
            sftp_client.upload_error_file(error_orders_csv)


def _process_file(file, lightspeed_client, lightspeed_shipment_id, lightspeed_shipment_value_id):
    skipped_orders = []
    processed_orders = []

    for row in file:
        try:
            order_id = _process_row(row, lightspeed_client, lightspeed_shipment_id, lightspeed_shipment_value_id)
            log.debug(f"Order {order_id} has been successfully created")
            order = _create_order_confirmation(order_id, row)
            processed_orders.append(order)
        except ProcessOrderException:
            log.warning(f"Skipping order {row[CSV_ORDER_ID_COL]}")
            skipped_orders.append(row)

    return processed_orders, skipped_orders


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
        log.error(err_message)
        raise ProcessOrderException(err_message)

    if not checkout["shipment_method"]:
        err_message = (f"Failed to add shipment method to checkout {checkout_id}\n"
                       f"Checkout: {checkout}")
        log.error(err_message)
        raise ProcessOrderException(err_message)

    validation = lightspeed_client.validate_checkout(checkout_id)

    if not validation["validated"]:
        err_message = (f"Checkout {checkout_id} haven't passed validation\n"
                       f"Validation errors: {validation['errors']}\n"
                       f"Checkout: {checkout}")
        log.error(err_message)
        raise ProcessOrderException(err_message)

    order_id = lightspeed_client.finish_checkout(checkout_id)

    payment_status = _generate_payment_status()
    order = lightspeed_client.update_order_payment_status(order_id, payment_status)
    if order["paymentStatus"] != "paid":
        err_message = f"Failed to update payment status of order {order_id}"
        log.error(err_message)
        raise ProcessOrderException(err_message)

    return order_id


# TODO: implement
def _create_processed_orders_csv(processed_orders):
    timestamp = datetime.now()
    file_name = f"H-{timestamp.strftime('%Y%m%d-%H%M')}.csv"
    file_path = os.path.join(TMP_FOLDER, file_name)

    log.debug(f"Creating file {file_path} with processed orders")
    with open(file_path, "w") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=_get_confirmation_csv_header(), dialect=CSV_DIALECT)
        writer.writeheader()
        writer.writerows(processed_orders)

        csvfile.close()

    return file_path


def _create_error_orders_csv(error_orders, csv_header):
    timestamp = datetime.now()
    file_name = f"PO-{timestamp.strftime('%Y%m%d-%H%M')}.csv"
    file_path = os.path.join(TMP_FOLDER, file_name)

    log.debug(f"Creating file {file_path} with error orders")
    with open(file_path, "w") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_header, dialect=CSV_DIALECT)
        writer.writeheader()
        writer.writerows(error_orders)

        csvfile.close()

    return file_path


CSV_ORDER_ID_COL = "Belegnummer"
CSV_FIRST_NAME_COL = "Lieferadresse_Vorname"
CSV_LAST_NAME_COL = "Lieferadresse_Nachname"
CSV_EMAIL_COL = "Belegnummer"
EMAIL_SUFFIX = "@westfalia.eu"
CSV_ADDRESS_STREET_COL = "Lieferadresse_Strasse"
CSV_ADDRESS_HOUSE_COL = "Lieferadresse_Hausnummer"
CSV_COMPANY_COL = "Lieferadresse_Firma"
CSV_ZIP_COL = "Lieferadresse_Postleitzahl"
CSV_CITY_COL = "Lieferadresse_Ort"
CSV_COUNTRY_COL = "Lieferadresse_Land"
CSV_EAN_COL = "Artikelnummer"
CSV_QUANTITY_COL = "Menge"
CSV_PRICE_COL = "EK-Preis"
CSV_POSITION_NUM_COL = "Positionsnummer"
CSV_STATUS_COL = "Status"


def _generate_checkout(row):
    """
    Creates Lightspeed checkout object from a given CSV file row. See https://developers.lightspeedhq.com/ecom/endpoints/checkout/#post-create-a-new-checkout
    :param row: (str) a single line from CSV file obtained from SFTP server
    :return: a checkout dictionary representation
    """

    customer = {
        "firstname": row[CSV_FIRST_NAME_COL],
        "lastname": row[CSV_LAST_NAME_COL],
        "email": row[CSV_EMAIL_COL] + EMAIL_SUFFIX,
        "phone": "0"
    }

    billing_address = {
        "name": row[CSV_FIRST_NAME_COL] + " " + row[CSV_LAST_NAME_COL],
        "address1": row[CSV_ADDRESS_STREET_COL] + " " + row[CSV_ADDRESS_HOUSE_COL],
        "address2": row[CSV_COMPANY_COL],
        "zipcode": row[CSV_ZIP_COL],
        "city": row[CSV_CITY_COL],
        "country": row[CSV_COUNTRY_COL],
        # House number should be empty as has been agreed with business
        "number": "-1"
    }

    shipping_address = {
        "name": row[CSV_FIRST_NAME_COL] + " " + row[CSV_LAST_NAME_COL],
        "address1": row[CSV_ADDRESS_STREET_COL] + " " + row[CSV_ADDRESS_HOUSE_COL],
        "address2": row[CSV_COMPANY_COL],
        # House number should be empty as has been agreed with business
        "number": "-1",
        "zipcode": row[CSV_ZIP_COL],
        "city": row[CSV_CITY_COL],
        "country": row[CSV_COUNTRY_COL]
    }

    order = {
        "customer": customer,
        "billing_address": billing_address,
        "shipping_address": shipping_address,
        # TODO: find out if notifications needed since emails are non-existing
        "notification": False
    }
    return order


def _get_variant_id(row, lightspeed_client):
    product_ean = row[CSV_EAN_COL]

    variants = lightspeed_client.get_all_product_variants()

    for variant in variants:
        if variant["ean"] == product_ean:
            return variant["id"]

    err_message = f"Cannot find product variant with EAN {product_ean}"
    log.error(err_message)
    raise ProcessOrderException(err_message)


def _generate_product_for_checkout(row, variant_id):
    product_quantity = row[CSV_QUANTITY_COL]
    product_price = row[CSV_PRICE_COL]
    country = row[CSV_COUNTRY_COL]

    product = {
        "variant_id": variant_id,
        "quantity": product_quantity
    }

    # Business requirement
    if country == "NL":
        product["special_price_incl"] = product_price
    else:
        product["special_price_excl"] = product_price

    return product


def _generate_shipment_and_payment_methods(lightspeed_shipment_id, lightspeed_shipment_value_id):
    shipment_method = {
        "id": "core|" + lightspeed_shipment_id + "|" + lightspeed_shipment_value_id
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

    order_dict = OrderedDict()
    order_dict[CSV_ORDER_ID_COL] = order_id
    order_dict[CSV_POSITION_NUM_COL] = row[CSV_POSITION_NUM_COL]
    order_dict[CSV_QUANTITY_COL] = row[CSV_QUANTITY_COL]
    order_dict[CSV_STATUS_COL] = 'confirmed'

    return order_dict


def _get_confirmation_csv_header():
    return [CSV_ORDER_ID_COL, CSV_POSITION_NUM_COL, CSV_QUANTITY_COL, CSV_STATUS_COL, "Trackingnummer", "Frachtfuehrer",
            "Trackinglink", "Warenausgangsdatum"]


def run(config_path):
    """
    Runs the entire application

    :param config_path: (str) path to the application config file
    :return: exit code 0 if terminated successfully, 1 otherwise
    """

    # get values from the config file
    from shared.config_parser import ConfigParser
    config_parser = None
    try:
        config_parser = ConfigParser(config_path)
    except yaml.YAMLError as e:
        log.critical("Load of config file %s failed. Check correctness of the config file.", config_path)
        return 1

    sftp_client = config_parser.create_sftp_client()
    if not sftp_client:
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

    # Register CSV dialect
    csv.register_dialect(CSV_DIALECT, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n")

    _process_files(sftp_client, lspeed_client, lspeed_shipment_id, lspeed_shipment_value_id)

    # Test code
    # file = None
    # try:
    #     file = open("SAMPLE.csv", "r")
    #     parsed_file = csv.DictReader(file, delimiter=';')
    #
    #     (processed_orders, skipped_orders) = _process_file(parsed_file, lspeed_client, lspeed_shipment_id,
    #                                                        lspeed_shipment_value_id)
    #     error_orders_csv = _create_error_orders_csv(skipped_orders, parsed_file.fieldnames)
    #     sftp_client.upload_error_file(error_orders_csv)
    # finally:
    #     if file:
    #         file.close()

    log.debug(f"Removing temp '{TMP_FOLDER}' folder")
    os.removedirs(TMP_FOLDER)
    return 0
