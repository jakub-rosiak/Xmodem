from Xmodem import Xmodem

modem = Xmodem("COM6")

modem.create_connection()
print("Connected")

modem.receive_file("./test1.txt")
print("Sent file")

modem.close()
print("Closed")