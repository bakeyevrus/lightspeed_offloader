import csv
import logging
from .const import FILE_TIMESTAMP_PATTERN

log = logging.getLogger(__name__)

"""The name of custom CSV dialect registered at the start of the app."""
CSV_DIALECT_NAME = "dial"

# Register CSV dialect
csv.register_dialect(CSV_DIALECT_NAME, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n")


def save_orders_as_csv(folder_path: str, orders, fieldnames, timestamp_offset: int = 1):
    """
    Serializes processed orders into CSV file.
    Note, that the method caller is responsible to create folder for a provided folder path.
    :param folder_path: (str) an absolute path to the folder to store the output CSV file.
    :param orders: (arr) an array of orders represented as dictionary to serialize
    :param fieldnames: (arr) an array of CSV headers
    :param timestamp_offset: (number) number of minutes to add to the timestamp, which is used in file name
    :return: an absolute path to the created CSV file
    """

    import os
    from datetime import datetime, timedelta

    timestamp = datetime.now() + timedelta(minutes=timestamp_offset)
    file_name = f"S-{timestamp.strftime(FILE_TIMESTAMP_PATTERN)}.csv"
    file_path = os.path.join(folder_path, file_name)

    log.debug(f"Creating file {file_path} with processed orders")
    with open(file_path, "w") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, dialect=CSV_DIALECT_NAME)
        writer.writeheader()
        writer.writerows(orders)

        csvfile.close()

    return file_path
