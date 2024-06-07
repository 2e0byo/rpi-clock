# ruff: noqa: ERA001
from pathlib import Path

from structlog import get_logger

from .fadeable import Fadeable

logger = get_logger()


class Lcd:
    BACKSPACE = "\b"
    CLEAR = "\f"
    HOME = "\x1b[H"
    BLINK = "\x1b[LB"
    NOBLINK = "\x1b[Lb"
    GOTOX = "\x1b[Lx"
    GOTOY = "\x1b[Ly"
    GOTO = "\x1b[Lx{:03}y{:03};"
    RESTART = "\x1b[LI"
    NEWCHAR = "\x1b[LG{}{:016};"
    CURSOR = "\x1b[LC"
    NOCURSOR = "\x1b[Lc"

    def __init__(
        self,
        rows: int = 2,
        cols: int = 16,
        path: Path = Path("/dev/lcd"),
        backlight: Fadeable | None = None,
    ):
        self.path = Path(path)
        self.rows = rows
        self.cols = cols
        self.backlight = backlight
        self._buffer = [""] * rows
        self._specials = {}
        self._trans = str.maketrans({})
        self.restart()

    def restart(self):
        """Restart lcd."""
        self._write(self.RESTART)
        self.cursor(False)
        self.blink(False)

    def cursor(self, val: bool):
        """Show or hide cursor."""
        self._write(self.CURSOR if val else self.NOCURSOR)

    def blink(self, val: bool):
        self._write(self.BLINK if val else self.NOBLINK)

    def goto(self, x: int, y: int):
        """Move the cursor to x,y."""
        self._write(self.GOTO.format(x, y))

    def _write(self, s: str):
        logger.debug("Writing to lcd", data=s.encode())
        self.path.write_text(s)

    def newchar(self, alias: str, char: bytearray):
        """Create a new character with an alias."""
        # index = len(self._specials) + 1 % 7
        # self._write(self.NEWCHAR.format(keys, "".join(hex(b)[2:] for b in char)))
        # self._specials[alias] = index.to_bytes(1, "big")
        # self._trans = str.maketrans(self._specials)

    def __setitem__(self, line: int, msg: str):
        """Set a line of the display to a string."""
        msg = f"{msg:{self.cols}.{self.cols}}"
        if self._buffer[line] != msg:
            msg = msg.translate(self._trans)
            logger.debug("Writing line to lcd", line=line, msg=msg)
            self._buffer[line] = msg
            self.goto(0, line)
            self._write(msg)
