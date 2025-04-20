from Xmodem import Xmodem

modem = Xmodem("COM5")

modem.create_connection()
print("Connected")

modem.send_file("./test.txt")
print("Sent file")

response = modem.receive_data()
print("Received: ", response)

modem.close()
print("Closed")