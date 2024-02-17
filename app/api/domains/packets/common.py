from pathlib import Path
from app.constants.aeris_features import AerisFeatures
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


OSU_API_V2_CHANGELOG_URL = "https://osu.ppy.sh/api/v2/changelog"

BEATMAPS_PATH = Path.cwd() / ".data/osu"

BASE_DOMAIN = app.settings.DOMAIN

AERIS_SERVER_FEATURES = AerisFeatures.Groups
if (app.settings.CHEAT_SERVER):
    AERIS_SERVER_FEATURES |= AerisFeatures.Cheats

# TODO: dear god
NOW_PLAYING_RGX = re.compile(
    r"^\x01ACTION is (?:playing|editing|watching|listening to) "
    rf"\[https://(?:osu\.)?(?:{re.escape(BASE_DOMAIN)}|ppy\.sh)/beatmapsets/(?P<sid>\d{{1,10}})#/?(?:osu|taiko|fruits|mania)?/(?P<bid>\d{{1,10}})/? .+\]"
    r"(?: <(?P<mode_vn>Taiko|CatchTheBeat|osu!mania)>)?"
    r"(?P<mods>(?: (?:-|\+|~|\|)\w+(?:~|\|)?)+)?\x01$",
)
OLD_NOW_PLAYING_RGX = re.compile(
    r"^\x01ACTION is (?:playing|editing|watching|listening to) "
    rf"\[(?:https?://)?(?:osu\.)?(?:{re.escape(BASE_DOMAIN)}|ppy\.sh)/b/(?P<bid>\d{{1,10}}) .+\]"
    r"(?: <(?P<mode_vn>Taiko|CatchTheBeat|osu!mania)>)?"
    r"(?P<mods>(?: (?:-|\+|~|\|)\w+(?:~|\|)?)+)?\x01$",
)

motds = [
    "PANIGE Lazy Boi", 
    "This Server Is sponsored by Raid Sh- oh... it's sponsored by nothing", 
    "Winners don't do drugs, unless it's steroids... In which case, DO LOTS OF DRUGS",
    "Inherited Flame Cancer",
    "Hug ?", 
    "PP when?", 
    ":thinking:"
]