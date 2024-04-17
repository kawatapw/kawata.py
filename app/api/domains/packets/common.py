from pathlib import Path
import app.packets
import app.settings
import app.state
import app.usecases.performance
import app.utils
from collections.abc import Callable
import re

from app.packets import ClientPackets
from app.packets import BasePacket

def register(
    packet: ClientPackets,
    restricted: bool = False,
) -> Callable[[type[BasePacket]], type[BasePacket]]:
    """Register a handler in `app.state.packets`."""

    def wrapper(cls: type[BasePacket]) -> type[BasePacket]:
        app.state.packets["all"][packet] = cls

        if restricted:
            app.state.packets["restricted"][packet] = cls

        return cls

    return wrapper