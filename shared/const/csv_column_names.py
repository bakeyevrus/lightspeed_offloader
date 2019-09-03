"""
This module contains names of the important columns of processed CSV files.
"""


class ExportedOrderCSV:
    ORDER_ID = "Belegnummer"
    FIRST_NAME = "Lieferadresse_Vorname"
    LAST_NAME = "Lieferadresse_Nachname"
    # Business requirement, email is derived from ORDER_ID
    EMAIL = "Belegnummer"
    ADDRESS_STREET = "Lieferadresse_Strasse"
    ADDRESS_HOUSE = "Lieferadresse_Hausnummer"
    COMPANY = "Lieferadresse_Firma"
    ZIP = "Lieferadresse_Postleitzahl"
    CITY = "Lieferadresse_Ort"
    COUNTRY = "Lieferadresse_Land"
    EAN = "Artikelnummer"
    QUANTITY = "Menge"
    PRICE = "EK-Preis"
    POSITION_NUM = "Positionsnummer"


class OrderConfirmationCSV:
    ORDER_ID = "Belegnummer"
    POSITION_NUM = "Positionsnummer"
    QUANTITY = "Menge"
    STATUS = "Status"
    TRACKING_NUMBER = "Trackingnummer"
    SHIPMENT_CARRIER = "Frachtfuehrer"
    TRACKING_LINK = "Trackinglink"
    ESTIMATED_SHIPMENT_DATE = "Warenausgangsdatum"

    """CSV file headers"""
    FIELDNAMES = [ORDER_ID, POSITION_NUM, QUANTITY, STATUS, TRACKING_NUMBER, SHIPMENT_CARRIER,
                  TRACKING_LINK, ESTIMATED_SHIPMENT_DATE]
