from pathlib import Path
from .fadeable import Fadeable


class Lcd:
    BACKSPACE = "\b"
    CLEAR = "\f"
    HOME = "\x1b[H"
    BLINK = "\x1b[LB"
    GOTOX = "\x1b[Lx"
    GOTOY = "\x1b[Ly"
    GOTO = "\x1b[Lx{:03}y{:03};"
    RESTART = "\x1b[LI"
    NEWCHAR = "\x1b[LG{}{:016};"
    CURSOR = "\x1b[LC"
    NOCURSOR = "\x1b[Lc"

    def __init__(
        self,
        lines: int = 2,
        cols: int = 16,
        path: Path = Path("/dev/lcd"),
        backlight: Fadeable = None,
    ):
        self.path = Path(path)
        self.lines = lines
        self.cols = cols
        self.backlight = backlight
        self._buffer = [""] * lines
        self._specials = {}
        self._trans = str.maketrans({})
        self.restart()
        self.cursor(False)

    def restart(self):
        self.write(self.RESTART)

    def cursor(self, val: bool):
        self.write(self.CURSOR if val else self.NOCURSOR)

    def goto(self, x: int, y: int):
        self.write(self.GOTO.format(x, y))

    def write(self, s: str):
        with self.path.open("w") as f:
            f.write(s)

    def newchar(self, alias: str, char: bytearray):
        index = len(self.specials.keys()) + 1 % 7
        self.write(self.NEWCHAR.format(keys, "".join(hex(b)[2:] for b in char)))
        self._specials[alias] = index.to_bytes(1, "big")
        self._trans = str.maketrans(self._specials)

    def __setitem__(self, line: int, msg: str):
        msg = f"{msg:{self.cols}.{self.cols}}"
        if self._buffer[line] != msg:
            self._buffer[line] = msg
            self.goto(0, line)
            self.write(msg.translate(self._trans))

    def __del__(self):
        if self.backlight:
            del self.backlight
