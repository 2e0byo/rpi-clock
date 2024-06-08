from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from logging import getLogger
from typing import Callable, Optional, Union

from . import run
from .lcd import Lcd


class Display(ABC):
    """A display, which may be showing one of several screens."""

    def __init__(
        self,
        rows: int,
        cols: int,
    ):
        """Initialise a new Display()."""
        self._current_screen = None
        self._screens = {}
        self.rows = rows
        self.cols = cols

    def get_screen(self, screen_name: str) -> str:
        """Get a screen by name."""
        return self._screens[screen_name]

    def new_screen(self, screen_name: str) -> Screen:
        """Generate a new screen for this display."""
        s = Screen(rows=self.rows, cols=self.cols, display=self, name=screen_name)
        self.add_screen(s)
        return s

    def add_screen(self, screen: Screen):
        """Add a screen."""
        if not isinstance(screen, Screen):
            raise TypeError("screen must be a Screen().")
        self._screens[screen.name] = screen
        if not self.current_screen:
            self.current_screen = screen

    def pop_screen(self, screen_name: str) -> Screen:
        """Pop a screen."""
        return self._screens.pop(screen_name)

    @abstractmethod
    def display(self) -> None:
        """Display the current screen on the hardware."""

    def update(self, screen: str):
        """Be notified that a screen has updated."""
        if self.current_screen is screen:
            self.display()

    @property
    def current_screen(self) -> Screen:
        """Get the current screen."""
        return self._current_screen

    @current_screen.setter
    def current_screen(self, screen: Screen):
        """Set the current screen."""
        if screen.name not in self._screens:
            raise ValueError(f"No such screen: {screen}")
        self._current_screen = self._screens[screen.name]
        self.display()


class MockDisplay(Display):
    """A mock display."""

    def __init__(self, *args, **kwargs):
        """Set up a new mock display."""
        super().__init__(*args, **kwargs)
        from unittest.mock import Mock

        self.display_mock = Mock()

    def display(self):
        """Display the screen."""
        self.display_mock()


class LcdDisplay(Display):
    """A display shown on an alphanumeric lcd."""

    def __init__(self, *args, lcd: Lcd, **kwargs):
        """Initialise a new LcdDisplay()."""
        rows = kwargs.pop("rows", lcd.rows)
        cols = kwargs.pop("cols", lcd.cols)
        super().__init__(*args, rows=rows, cols=cols, **kwargs)
        self._lcd = lcd

    def display(self):
        """Display a particular screen on the lcd."""
        for i, row in enumerate(self.current_screen):
            self._lcd[i] = row


class Screen:
    """A screen on a display."""

    def __init__(self, *, rows: int, cols: int, display: Display, name: str):
        """Set up a new screen."""
        self.rows = rows
        self.cols = cols
        self._store = [" " * cols] * rows
        self.display = display
        self.name = name

    def __getitem__(self, row: int, col: Union[int, slice, None] = None) -> str:
        """Get the contents of a line on the screen, optionally slicing it."""
        line = self._store[row]
        if col:
            line = line[col]
        return line

    def __setitem__(self, where, msg: str) -> None:
        if isinstance(where, tuple):
            row, col = where
            line = list(self._store[row])
            line[col] = list(msg)
            self._store[row] = "".join(line) + " " * (self.cols - len(line))
        else:
            self._store[where] = msg + " " * (self.cols - len(msg))
        self.display.update(self)

    def __repr__(self):
        return f"Screen(rows={self.rows}, cols={self.cols}, display={self.display}, name={self.name})"  # noqa: E501


@dataclass
class MenuItem:
    """An item in a menu."""

    next: MenuItem
    prev: MenuItem
    screen: Screen
    enter: MenuItem
    entry_fn: Optional[Callable] = None
    load_fn: Optional[Callable] = None


class Menu:
    def __init__(self, name, item: MenuItem):
        item.next = item
        item.prev = item
        self.current_item = item
        self._logger = getLogger(name)

    async def next(self, *_):
        """Go to next screen."""
        self.current_item = self.current_item.next
        await self.load()

    async def prev(self, *_):
        """Go to prev screen."""
        self.current_item = self.current_item.prev
        await self.load()

    async def enter(self, *_):
        """Enter."""
        self.current_item = self.current_item.enter
        await run(self.current_item.entry_fn)
        await self.load()

    async def load(self):
        """Load current screen."""
        self._logger.debug(f"Screen is now {self.current_item.screen}")
        self.current_item.screen.display.current_screen = self.current_item.screen
        await run(self.current_item.load_fn)

    def new_after(self, item: MenuItem | None = None, **kwargs):
        """Generate a new item after the given or current item."""
        if not item:
            item = self.current_item
        new = MenuItem(prev=item.prev, next=item.next, **kwargs)
        if not new.enter:
            new.enter = new
        item.next = new
