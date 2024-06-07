"""Endpoint templates for fastapi."""

from abc import ABC
from typing import Generic, TypeVar

from fastapi.routing import APIRouter

ThingT = TypeVar("ThingT")


class Endpoint(ABC, Generic[ThingT]):
    """An endpoint."""

    def __init__(self, *, thing: ThingT, prefix: str):
        """Initialise a new Endpoint."""
        self.router = APIRouter(prefix=prefix, tags=[prefix[1:]])
        self.thing: ThingT = thing
