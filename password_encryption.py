import sys
import argparse
import base64
from getpass import getpass as GP
from Crypto.Cipher import AES
from Crypto import Random

BS = 16


def __pad(s):
    return s + (BS - len(s) % BS) * chr(BS - len(s) % BS)


def __unpad(s):
    return s[0:-ord(s[-1])]


def encrypt(password, master_pass, file=None):
    """Encrypts given password against master password. Additionally stores it
    into the file, if the path is provided

    Parameters:
        password (str) - password to encrypt
        master_pass (str) - master password used for encryption
        file (str) - path to the file to store the password
    """
    cipher = AES.new(__pad(master_pass), AES.MODE_ECB)
    cpassword = cipher.encrypt(__pad(password))

    cpassword = base64.encodebytes(cpassword).decode('utf-8')
    base64.encodebytes

    if file:
        with open(file, 'w') as file:
            file.write(cpassword)
            file.close()

    return cpassword.strip()


def main():
    parser = argparse.ArgumentParser(
                                    description="""Encrypts password with
                                    master password""")
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

    encrypt(password, master_pass, file=args.write)
    print('DONE')


if __name__ == '__main__':
    sys.exit(main())
