import ctypes
from ctypes import wintypes
from enum import Enum

from commtimeouts import COMMTIMEOUTS
from dcb import DCB

class CheckMode(Enum):
    Checksum = "checksum"
    CRC = "crc"


def calculate_crc(data: bytes) -> bytes:
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc.to_bytes(2, 'big')


class Xmodem:
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    SOH = 0x01
    ACK = 0x06
    NAK = 0x15
    EOT = 0x04
    CAN = 0x18
    SUB = 0x1A
    C = b'C'
    BLOCK_SIZE = 128
    MAX_RETRIES = 10
    MAX_RECEIVE_RETRIES = 6

    def __init__(self, port):
        self.port = f"\\\\.\\{port}"
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.handle = None

    def __enter__(self):
        self.create_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def create_connection(self):
        self.handle = self.kernel.CreateFileW(
            self.port,
            self.GENERIC_READ | self.GENERIC_WRITE,
            0,
            None,
            self.OPEN_EXISTING,
            0,
            None
        )

        if self.handle == self.INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())

        self.configure_serial()

    def send_data(self, data: bytes) -> wintypes.DWORD:
        written = wintypes.DWORD()
        success = self.kernel.WriteFile(
            self.handle,
            data,
            len(data),
            ctypes.byref(written),
            None,
        )
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())
        return written

    def receive_data(self, buffer_size: int = 128) -> bytes:
        buffer = ctypes.create_string_buffer(buffer_size)
        read = wintypes.DWORD()
        success = self.kernel.ReadFile(
            self.handle,
            buffer,
            ctypes.sizeof(buffer),
            ctypes.byref(read),
            None,
        )
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.raw[:read.value]

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None

    def configure_serial(self, baudrate=9600, bytesize=8, parity=0, stopbits=1, read_interval=50, read_total_timeout_constant=10000, read_total_timeout_multiplier=0):
        dcb = DCB()
        dcb.DCBlength = ctypes.sizeof(dcb)

        if not self.kernel.GetCommState(self.handle, ctypes.byref(dcb)):
            raise ctypes.WinError(ctypes.get_last_error())

        dcb.BaudRate = baudrate
        dcb.ByteSize = bytesize
        dcb.Parity = parity
        dcb.StopBits = stopbits
        dcb.fBinary = 1
        dcb.fParity = 0
        dcb.fDtrControl = 1
        dcb.fRtsControl = 1

        if not self.kernel.SetCommState(self.handle, ctypes.byref(dcb)):
            raise ctypes.WinError(ctypes.get_last_error())

        timeouts = COMMTIMEOUTS()
        timeouts.ReadIntervalTimeout = read_interval
        timeouts.ReadTotalTimeoutConstant = read_total_timeout_constant
        timeouts.ReadTotalTimeoutMultiplier = read_total_timeout_multiplier
        timeouts.WriteTotalTimeoutConstant = 1000
        timeouts.WriteTotalTimeoutMultiplier = 10
        print("Set timeouts")
        if not self.kernel.SetCommTimeouts(self.handle, ctypes.byref(timeouts)):
            raise ctypes.WinError(ctypes.get_last_error())

    def send_file(self, file_path: str) -> bool:
        with open(file_path, "rb") as f:
            for i in range(self.MAX_RECEIVE_RETRIES):
                byte = self.receive_data(1)
                if byte == bytes([self.NAK]):
                    checksum_type = CheckMode.Checksum
                    print("Received first NAK")
                    break
                elif byte == self.C:
                    checksum_type = CheckMode.CRC
                    print("Received first C")
                    break
                else:
                    print("Didn't receive start transmission request, aborting...")
                    return False

            if checksum_type not in (CheckMode.Checksum, CheckMode.CRC):
                self.send_data(bytes([self.CAN]))
                raise ValueError("Unknown error checking type, aborting...")

            block_num = 1

            while True:
                data = f.read(self.BLOCK_SIZE)
                if not data:
                    break

                if len(data) < self.BLOCK_SIZE:
                    data += bytes([self.SUB]) * (self.BLOCK_SIZE - len(data))

                packet = bytes([
                    self.SOH,
                    block_num % 256,
                    255 - (block_num % 256),
                ]) + data
                if checksum_type == CheckMode.Checksum:
                    packet += bytes([sum(data) & 0xff])
                elif checksum_type == CheckMode.CRC:
                    packet += calculate_crc(data)

                print(f'Sending packet {block_num}: {packet}')
                for _ in range(self.MAX_RETRIES):
                    self.send_data(packet)

                    received_data = self.receive_data(1)
                    if not received_data:
                        continue

                    response = received_data[0]

                    if response == self.ACK:
                        print("Received ACK")
                        block_num += 1
                        break
                    else:
                        print("Received NAK")
                        continue
                else:
                    self.send_data(bytes([self.CAN]))
                    print("Failed")
                    return False

            for _ in range(self.MAX_RETRIES):
                print("EOT sent")
                self.send_data(bytes([self.EOT]))
                if self.receive_data(1) == bytes([self.ACK]):
                    print("Received ACK")
                    return True

            return False

    def receive_file(self, file_path: str, checksum_type: CheckMode) -> bool:
        if checksum_type not in (CheckMode.Checksum, CheckMode.CRC):
            self.send_data(bytes([self.CAN]))
            raise ValueError("Unknown error checking type, aborting...")
        first_byte = None
        for i in range(self.MAX_RECEIVE_RETRIES):
            if checksum_type == CheckMode.Checksum:
                self.send_data(bytes([self.NAK]))
                print(f"Sent NAK ({i+1}/{self.MAX_RECEIVE_RETRIES})")
            elif checksum_type == CheckMode.CRC:
                self.send_data(self.C)
                print(f"Sent C ({i+1}/{self.MAX_RECEIVE_RETRIES})")

            response = self.receive_data(1)
            if response:
                first_byte = response[0]
                if first_byte == self.SOH:
                    print("Received SOH")
                    break

        if first_byte != self.SOH:
            print(f"Failed to receive SOH after {self.MAX_RECEIVE_RETRIES} tries, aborting.")
            return False
        expected_block = 1
        file_data = bytearray()

        while True:
            end_of_transmission = False
            for _ in range(self.MAX_RETRIES):
                if first_byte is None:
                    for _ in range(self.MAX_RECEIVE_RETRIES):
                        received_data = self.receive_data(1)
                        if not received_data:
                            print("Didn't receive any data")
                            continue

                        first_byte = received_data[0]

                        if first_byte == self.EOT:
                            self.send_data(bytes([self.ACK]))
                            print("EOT Received, Sending ACK")
                            end_of_transmission = True
                            break

                        elif first_byte == self.SOH:
                            print("Received SOH")
                            break

                        else:
                            print("Invalid byte Received, waiting for SOH")
                    else:
                        self.send_data(bytes([self.CAN]))
                        print("Connection failed, aborting...")
                        return False

                if end_of_transmission:
                    break

                first_byte = None

                packet = None
                if checksum_type == CheckMode.Checksum:
                    packet = self.receive_data(self.BLOCK_SIZE + 3)
                elif checksum_type == CheckMode.CRC:
                    packet = self.receive_data(self.BLOCK_SIZE + 4)

                print(f"Received packet {expected_block}: {packet}")

                block_num = packet[0]
                block_inv = packet[1]
                data = packet[2:2 + self.BLOCK_SIZE]
                checksum_start = 2 + self.BLOCK_SIZE
                checksum_end = None
                if checksum_type == CheckMode.Checksum:
                    checksum_end = checksum_start + 1
                elif checksum_type == CheckMode.CRC:
                    checksum_end = checksum_start + 2

                checksum = packet[checksum_start:checksum_end]

                print(f"Checksum: {checksum}")

                if block_num % 256 !=  (255 - block_inv) % 256:
                    self.send_data(bytes([self.NAK]))
                    print("Invalid block number received, Sending NAK")
                    continue

                if checksum_type == CheckMode.Checksum:
                    calc_checksum = (sum(data) & 0xff).to_bytes(1, 'little')
                    if calc_checksum != checksum:
                        self.send_data(bytes([self.NAK]))
                        print("Invalid checksum received, Sending NAK")
                        continue
                elif checksum_type == CheckMode.CRC:
                    calc_checksum = calculate_crc(data)
                    if calc_checksum != checksum:
                        self.send_data(bytes([self.NAK]))
                        print("Invalid checksum received, Sending NAK")
                        continue

                if block_num != expected_block % 256:
                    self.send_data(bytes([self.NAK]))
                    print("Invalid block number received, Sending NAK")
                    continue

                file_data.extend(data)
                expected_block += 1

                self.send_data(bytes([self.ACK]))
                break

            else:
                self.send_data(bytes([self.CAN]))
                print("Connection failed, aborting...")
                return False

            if end_of_transmission:
                break

        file_data = bytes(file_data).rstrip(bytes([self.SUB]))

        try:
            with open(file_path, "wb") as f:
                f.write(file_data)
            print(f"File written to {file_path}")
            return True
        except Exception as e:
            print(f"Failed to write to {file_path}: {e}")
            return False
