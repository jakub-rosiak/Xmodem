import ctypes
from ctypes import wintypes

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

    def send_file(self, file_path):
        with open(file_path, "rb") as f:
            while True:
                if self.receive_data(1) == bytes([self.NAK]):
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
                ]) + data + bytes([sum(data) % 256])

                for _ in range(self.MAX_RETRIES):
                    self.send_data(packet)
                    response = self.receive_data(1)
                    if response == bytes([self.ACK]):
                        block_num += 1
                        break
                    elif response == bytes([self.NAK]):
                        continue
                    else:
                        self.send_data(bytes([self.CAN]))
                        return False
                else:
                    self.send_data(bytes([self.CAN]))
                    return False

            for _ in range(self.MAX_RETRIES):
                self.send_data(bytes([self.EOT]))
                if self.receive_data(1) == bytes([self.ACK]):
                    return True

            return False

    def receive_file(self, file_path):
        pass