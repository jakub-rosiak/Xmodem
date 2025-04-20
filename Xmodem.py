import ctypes
import errno
from ctypes import wintypes

from dcb import DCB


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
    BLOCK_SIZE = 128
    MAX_RETRIES = 10

    def __init__(self, port):
        self.port = f"\\\\.\\{port}"
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.handle = None

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

    def send_data(self, data: bytes):
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

    def receive_data(self, buffer_size: int = 128):
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

    def configure_serial(self, baudrate=9600, bytesize=8, parity=0, stopbits=1):
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

    def send_file(self, file_path):
        with open(file_path, "rb") as f:
            while True:
                if self.receive_data(1) == bytes([self.NAK]):
                    print("Received first NAK")
                    break

            block_num = 1

            while True:
                data = f.read(self.BLOCK_SIZE)
                if not data:
                    break

                if len(data) < self.BLOCK_SIZE:
                    data += b'\x1A' * (self.BLOCK_SIZE - len(data))

                packet = bytes([
                    self.SOH,
                    block_num % 256,
                    255 - (block_num % 256),
                ]) + data + bytes([sum(data) & 0xff])
                print(packet)
                for _ in range(self.MAX_RETRIES):
                    self.send_data(packet)

                    while True:
                        received_data = self.receive_data(1)
                        if received_data:
                            break

                    response = received_data[0]

                    if response == self.ACK:
                        print("Received ACK")
                        block_num += 1
                        break
                    elif response == self.NAK:
                        print("Received NAK")
                        continue
                    else:
                        self.send_data(bytes([self.CAN]))
                        print("Failed")
                        return False
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

    def receive_file(self, file_path):
        self.send_data(bytes([self.NAK]))
        print("Sent NAK")

        expected_block = 1
        file_data = bytearray()

        while True:

            end_of_transmission = False
            while True:
                received_data = self.receive_data(1)
                if not received_data:
                    continue

                first_byte = received_data[0]
                print(first_byte)

                if first_byte == self.EOT:
                    self.send_data(bytes([self.ACK]))
                    print("EOT Received, Sending ACK")
                    end_of_transmission = True
                    break

                if first_byte == self.SOH:
                    break
                else:
                    print("Invalid byte Received, waiting for SOH")

            if end_of_transmission:
                break

            packet = self.receive_data(self.BLOCK_SIZE + 3)

            print(f"Received packet {expected_block}: {packet}")

            block_num = packet[0]
            block_inv = packet[1]
            data = packet[2:2 + self.BLOCK_SIZE]
            checksum = packet[self.BLOCK_SIZE + 2]

            if block_num !=  (255 - block_inv):
                self.send_data(bytes([self.NAK]))
                print("Invalid block number received, Sending NAK")
                continue

            calc_checksum = sum(data) & 0xff
            if calc_checksum != checksum:
                self.send_data(bytes([self.NAK]))
                print("Invalid checksum received, Sending NAK")
                continue

            if block_num != expected_block:
                self.send_data(bytes([self.NAK]))
                print("Invalid block number received, Sending NAK")
                continue

            file_data.extend(data)
            expected_block += 1

            self.send_data(bytes([self.ACK]))

        file_data = bytes(file_data).rstrip(bytes([self.SUB]))
        with open(file_path, "wb") as f:
            f.write(file_data)
            return True