from structlog import get_logger

logger = get_logger()


class PinError(Exception):
    pass


class Pin:
    OUT = 0
    IN = 1
    instances = []

    def __init__(
        self,
        pi,
        pin: int,
        mode: int,
        inverted: bool = False,
        name: str | None = None,
    ):
        self.pi = pi
        self.pin = pin
        self.mode = mode
        self.inverted = inverted
        pi.set_mode(pin, mode)
        name = name or f"{__name__}-{len(self.instances)}"
        self.instances.append(name)
        self._logger = logger.bind(name=name)
        self._logger.debug(f"Set pin{pin} to mode {mode}.")

    def __call__(self, val=None):
        if val is None:
            val = self.pi.read(self.pin)
            return val if not self.inverted else not val

        if self.mode != self.OUT:
            raise PinError("Pin not in out mode")
        self.pi.write(self.pin, val if not self.inverted else not val)

    def on(self):
        self.__call__(1)

    def off(self):
        self.__call__(0)
