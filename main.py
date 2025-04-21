from pathlib import Path
import re
from Xmodem import Xmodem

def main_menu():
    print("=" * 10)
    print("     XMODEM FILE TRANSFER")
    print("=" * 10)

def get_port():
    while True:
        choice = input("\nSelect com port: ")

        if re.match(r'^COM\d+$', choice):
            return choice

def option_menu():
    while True:
        print("1. Send file")
        print("2. Receive file")
        choice = input("\n(1, 2): ")

        if choice in ["1", "2"]:
            return choice

def get_file(option):
    while True:
        file_path = input("\nEnter file path: ")

        if option == "1" and Path(file_path).is_file():
            return file_path

        elif option == "2" and Path(file_path).parent.exists():
            return file_path

        else:
            print("Invalid file path")

def get_checksum_type():
    while True:
        print("Select error detection method: ")
        print("1. Checksum")
        print("2. CRC")
        choice = input("\n(1, 2): ")
        if choice in ["1", "2"]:
            return choice

def main():
    main_menu()
    port = get_port()
    modem = Xmodem(port)

    print("Attempting connection...")
    modem.create_connection()
    print("Connected")

    option = option_menu()
    file_name = get_file(option)

    if option == "1":
        print("Sending file...")
        modem.send_file(file_name)

    elif option == "2":
        checksum_type = get_checksum_type()
        print("Receiving file...")
        modem.receive_file(file_name, checksum_type)

    print("Closing...")
    modem.close()
    print("Closed")

if __name__ == "__main__":
    main()