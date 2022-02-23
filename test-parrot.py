from time import sleep
from pigpio import pi

pi = pi()

MOSI = 10
MISO = 9
SCLK = 11
CS = 8
BAUD = 5000
MODE = 1
TESTS = 200

for _ in range(TESTS):
    pi.bb_spi_open(CS, MISO, MOSI, SCLK, BAUD, MODE)
    pi.bb_spi_xfer(CS, b"p\x02ab")
    sleep(0.001)
    print(pi.bb_spi_xfer(CS, [0] * 2))
    pi.bb_spi_close(CS)
    sleep(0.01)
