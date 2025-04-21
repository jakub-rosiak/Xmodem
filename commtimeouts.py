import ctypes
from ctypes import wintypes

class COMMTIMEOUTS(ctypes.Structure):
    _fields_ = [
        ('ReadIntervalTimeout', wintypes.DWORD),
        ('ReadTotalTimeoutMultiplier', wintypes.DWORD),
        ('ReadTotalTimeoutConstant', wintypes.DWORD),
        ('WriteTotalTimeoutMultiplier', wintypes.DWORD),
        ('WriteTotalTimeoutConstant', wintypes.DWORD),
    ]
