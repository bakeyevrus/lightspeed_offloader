import argparse
import base64
import sys
from getpass import getpass as GP
from Crypto.Cipher import AES

BS = 16


def _pad(s):
    return s + (BS - len(s) % BS) * chr(BS - len(s) % BS)


def _unpad(s):
    return s[0:-ord(s[-1])]


def decrypt(master_pass, file_path):
    """Decrypts password from the specified file.

    :param master_pass: (str) master password, which has been used for encryption
    :param file_path: (str) path to the file containing encrypted password

    :return: decrypted password as a string
    """

    # Create a decipher to decrypt the ciphertext
    cipher = AES.new(_pad(master_pass), AES.MODE_ECB)

    with open(file_path, 'r') as file:
        cpassword = file.read()
        file.close()
        cpassword = base64.b64decode(_pad(cpassword))
        password = _unpad(cipher.decrypt(cpassword).decode('utf-8'))
        return password.strip()


def encrypt(password, master_pass, file_path=None):
    """Encrypts given password against master password. Additionally stores it
    into the file, if the path is provided

    :param password: (str) password to encrypt
    :param master_pass: (str) - master password used for encryption
    :param file_path: (str) - path to the file to store the password

    :return: encrypted password as a string
    """

    cipher = AES.new(_pad(master_pass), AES.MODE_ECB)
    cpassword = cipher.encrypt(_pad(password))

    cpassword = base64.encodebytes(cpassword).decode('utf-8')

    if file_path:
        with open(file_path, 'w') as file:
            file.write(cpassword)
            file.close()

    return cpassword.strip()


def main():
    parser = argparse.ArgumentParser(description="""Encrypts password with master password""")
    parser.add_argument('-w', '--write',
                        nargs='?',
                        help='Path to store encrypted password',
                        type=str)
    args = parser.parse_args()

    if not args.write:
        parser.print_help()
        return 1

    master_pass = GP(prompt='Enter master password:', stream=None)
    print(master_pass)

    password = GP(prompt='Enter password:', stream=None)

    encrypt(password, master_pass, file_path=args.write)
    print('DONE')


if __name__ == '__main__':
    sys.exit(main())
