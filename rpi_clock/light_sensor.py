from smbus import SMBus


class LightSensor:
    """An ambient light sensor, reading in lux."""

    ADDRESS = 0x23
    POWER_DOWN = 0x00
    POWER_ON = 0x01
    RESET = 0x07
    ONE_TIME_HIGH_RES_MODE = 0x20
    CONTINUOUS_HIGH_RES_MODE = 0b0001_0000

    def __init__(self, addr: int = None):
        self.bus = SMBus(1)
        self.addr = addr or self.ADDRESS
        self.val = None

    def read(self):
        data = self.bus.read_i2c_block_data(self.addr, self.ONE_TIME_HIGH_RES_MODE)
        self.val = self.convert(data)
        return self.val

    def convert(self, data):
        return (data[1] + (256 * data[0])) / 1.2
