"""Fake reactive properties, i.e. callback wrappers."""

from typing import Any, Callable, Generic, Optional, TypeVar

from . import sync_run

ValueT = TypeVar("ValueT")


class Watched(Generic[ValueT]):
    """A value which should have some side-effect when it changes."""

    def __init__(
        self, val: Optional[ValueT] = None, callback: Optional[Callable] = None
    ) -> None:
        """Initialise a new watched value.

        Args:
            val (any): initial value to store.
            callback (Callable): called every time .value is changed,
                                 with the old and new values as arguments.
        """
        self._val = val
        self.callback = callback

    @property
    def value(self) -> ValueT | None:
        """Get current value."""
        return self._val

    @value.setter
    def value(self, val: Any) -> None:
        """Set value."""
        sync_run(self.callback, self._val, val)
        self._val = val
