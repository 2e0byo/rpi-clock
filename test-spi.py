from time import sleep
from pigpio import pi

pi = pi()

MOSI = 10
MISO = 9
SCLK = 11
CS = 8
BAUD = 5000
MODE = 1

print("parrot")
pi.bb_spi_open(CS, MISO, MOSI, SCLK, BAUD, MODE)
pi.bb_spi_xfer(CS, b"p\x02ab")
sleep(0.001)
print(pi.bb_spi_xfer(CS, [0] * 2))
pi.bb_spi_close(CS)

print("read")
pi.bb_spi_open(CS, MISO, MOSI, SCLK, BAUD, MODE)
pi.bb_spi_xfer(CS, b"r")
sleep(0.001)
print(pi.bb_spi_xfer(CS, [0] * 2))
pi.bb_spi_close(CS)

print("parrot")
pi.bb_spi_open(CS, MISO, MOSI, SCLK, BAUD, MODE)
pi.bb_spi_xfer(CS, b"p\x02cd")
sleep(0.001)
print(pi.bb_spi_xfer(CS, [0] * 2))
pi.bb_spi_close(CS)

print("write")
pi.bb_spi_open(CS, MISO, MOSI, SCLK, BAUD, MODE)
bb = b"s" + (1001).to_bytes(2, "little")
print(bb)
pi.bb_spi_xfer(CS, bb)
sleep(0.001)
print(int.from_bytes(pi.bb_spi_xfer(CS, [0] * 2)[1], "little"))
pi.bb_spi_close(CS)

print("read")
pi.bb_spi_open(CS, MISO, MOSI, SCLK, BAUD, MODE)
pi.bb_spi_xfer(CS, b"r")
sleep(0.001)
print(pi.bb_spi_xfer(CS, [0] * 2))
pi.bb_spi_close(CS)
