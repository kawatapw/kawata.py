"""
Collections Module - Global Data Collection Management

This module defines collection classes for managing global server state including
active players, chat channels, multiplayer matches, and player groups. These
collections serve as the central data structures for the osu! server, providing
efficient access patterns and maintaining consistency across the application.

The module implements specialized list classes with enhanced functionality for
fast lookups, automatic indexing, and integration with the caching system. Each
collection class provides methods for adding, removing, and querying items while
maintaining internal indexes for optimal performance.

Key Features:
    - Specialized collection classes for different entity types
    - Fast lookup by multiple keys (ID, name, token)
    - Automatic index maintenance on add/remove operations
    - Integration with database and caching systems
    - Privilege-based filtering and querying
    - Error handling with logging integration
    - Bulk operations for efficient data management

Integration Points:
    - Player session management in app/state/sessions.py
    - Database operations in app/repositories/
    - Cache management in app/state/cache.py
    - Packet handling in app/packets.py
    - Authentication in app/api/domains/cho.py

Collection Types:
    - Channels: Active chat channels with privilege-based access
    - Matches: Multiplayer matches with slot management
    - Groups: Player groups with invite and membership management
    - Players: Online players with multi-key indexing

Indexing Strategy:
    - Players indexed by token, ID, and safe name
    - Channels indexed by real name
    - Matches indexed by slot position
    - Groups indexed by leader name
    - All indexes maintained automatically on mutations

Usage Pattern:
    - Collections are initialized during server startup
    - Items are added/removed during player connections
    - Lookups use the most efficient index available
    - Bulk operations minimize database queries
    - Error handling ensures data consistency

Example Usage:
    # Get player by different methods
    player = players.get(token="abc123")
    player = players.get(id=12345)
    player = players.get(name="PlayerName")
    
    # Get channel by name
    channel = channels.get_by_name("#osu")
    
    # Get free match slot
    match_id = matches.get_free()
    
    # Check player privileges
    if player.priv & Privileges.STAFF:
        staff_players = players.staff

Related Files:
    - app/state/sessions.py: Session management using collections
    - app/objects/player.py: Player class stored in collections
    - app/objects/channel.py: Channel class stored in collections
    - app/objects/match.py: Match class stored in collections
    - app/objects/group.py: Group class stored in collections
"""

from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence
from typing import Any

import databases.core

import app.settings
import app.state
import app.utils
from app.constants.privileges import ClanPrivileges
from app.constants.privileges import Privileges
from app.logging import Ansi, log, error_catcher
from app.objects.channel import Channel
from app.objects.match import Match
from app.objects.player import Player
from app.objects.group import Group
from app.repositories import channels as channels_repo
from app.repositories import clans as clans_repo
from app.repositories import users as users_repo
from app.utils import make_safe_name


class Channels(list[Channel]):
    """The currently active chat channels on the server."""

    def __iter__(self) -> Iterator[Channel]:
        return super().__iter__()

    def __contains__(self, o: object) -> bool:
        """Check whether internal list contains `o`."""
        # Allow string to be passed to compare vs. name.
        if isinstance(o, str):
            return o in (chan.name for chan in self)
        else:
            return super().__contains__(o)

    def __repr__(self) -> str:
        # XXX: we use the "real" name, aka
        # #multi_1 instead of #multiplayer
        # #spect_1 instead of #spectator.
        return f'[{", ".join(c.real_name for c in self)}]'

    @error_catcher
    def get_by_name(self, name: str) -> Channel | None:
        """Get a channel from the list by `name`."""
        for channel in self:
            if channel.real_name == name:
                return channel

        return None

    @error_catcher
    def append(self, channel: Channel) -> None:
        """Append `channel` to the list."""
        super().append(channel)

        if app.settings.DEBUG_LEVEL >= 1:
            log(f"{channel} added to channels list.")

    @error_catcher
    def extend(self, channels: Iterable[Channel]) -> None:
        """Extend the list with `channels`."""
        super().extend(channels)

        if app.settings.DEBUG_LEVEL >= 1:
            log(f"{channels} added to channels list.")

    @error_catcher
    def remove(self, channel: Channel) -> None:
        """Remove `channel` from the list."""
        super().remove(channel)

        if app.settings.DEBUG_LEVEL >= 1:
            log(f"{channel} removed from channels list.")

    @error_catcher
    async def prepare(self) -> None:
        """Fetch data from sql & return; preparing to run the server."""
        log("Fetching channels from sql.", Ansi.LCYAN)
        for row in await channels_repo.fetch_many():
            self.append(
                Channel(
                    name=row["name"],
                    topic=row["topic"],
                    read_priv=Privileges(row["read_priv"]),
                    write_priv=Privileges(row["write_priv"]),
                    auto_join=row["auto_join"] == 1,
                ),
            )


class Matches(list[Match | None]):
    """The currently active multiplayer matches on the server."""

    def __init__(self) -> None:
        MAX_MATCHES = 64  # TODO: refactor this out of existence
        super().__init__([None] * MAX_MATCHES)

    def __iter__(self) -> Iterator[Match | None]:
        return super().__iter__()

    def __repr__(self) -> str:
        return f'[{", ".join(match.name for match in self if match)}]'

    @error_catcher
    def get_free(self) -> int | None:
        """Return the first free match id from `self`."""
        for idx, match in enumerate(self):
            if match is None:
                return idx

        return None

    @error_catcher
    def remove(self, match: Match | None) -> None:
        """Remove `match` from the list."""
        for i, _m in enumerate(self):
            if match is _m:
                self[i] = None
                break

        if app.settings.DEBUG_LEVEL >= 1:
            log(f"{match} removed from matches list.")

class Groups(list[Group]):
    """Active groups present on the server"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    
    def __iter__(self) -> Iterator[Group]:
        return super().__iter__()

    def __contains__(self, player: object) -> bool:
        # allow us to either pass in the player
        # obj, or the player name as a string.
        if isinstance(player, str):
            return player in (group.lead.name for group in self)
        else:
            return super().__contains__(player)

    def __repr__(self) -> str:
        return f'[{", ".join(map(repr, self))}]'

    @error_catcher
    def has_group(self, player: Player) -> bool:
        for group in self:
            if player in group.players:
                return True
        return False
    
    @error_catcher
    def get_group(self, player: Player) -> Group | None:
        for group in self:
            if player in group.players:
                return group
        return None
    
    @error_catcher
    def player_invites(self, player:Player) -> list[Group]:
        groups : list[Group] = []
        for group in self:
            if player in group.invites:
                groups.append(group)
        return groups
    
    @error_catcher
    def show_invite_str(self, player:Player) -> str:
        invites = self.player_invites(player)
        base = "You have {} Pending invites\n".format(len(invites)) 
        for x in invites:
            base += f"type !accept {x.lead.safe_name} to join {x.lead.name}'s group\n"
        if self.has_group(player):
            base += f"Warning !!! joining another group will make you leave the one you are in"
        return base

    @error_catcher
    def check_token(self, token:str) -> bool:
        for group in self:
            if group.token == token:
                return False
        return True

class Players(list[Player]):
    """The currently active players on the server."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._by_token: dict[str, Player] = {}
        self._by_id: dict[int, Player] = {}
        self._by_name: dict[str, Player] = {}

    def __iter__(self) -> Iterator[Player]:
        return super().__iter__()

    def __contains__(self, player: object) -> bool:
        if isinstance(player, str):
            return make_safe_name(player) in self._by_name
        else:
            return super().__contains__(player)

    def __repr__(self) -> str:
        return f'[{", ".join(map(repr, self))}]'

    @property
    @error_catcher
    def ids(self) -> set[int]:
        """Return a set of the current ids in the list."""
        return {p.id for p in self}

    @property
    @error_catcher
    def staff(self) -> set[Player]:
        """Return a set of the current staff online."""
        return {p for p in self if p.priv & Privileges.STAFF}

    @property
    @error_catcher
    def restricted(self) -> set[Player]:
        """Return a set of the current restricted players."""
        return {p for p in self if not p.priv & Privileges.UNRESTRICTED}

    @property
    @error_catcher
    def unrestricted(self) -> set[Player]:
        """Return a set of the current unrestricted players."""
        return {p for p in self if p.priv & Privileges.UNRESTRICTED}

    @error_catcher
    def enqueue(self, data: bytes, immune: Sequence[Player] = []) -> None:
        """Enqueue `data` to all players, except for those in `immune`."""
        for player in self:
            if player not in immune:
                player.enqueue(data)

    @error_catcher
    def get(
        self,
        token: str | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> Player | None:
        """Get a player by token, id, or name from cache."""
        if token is not None:
            return self._by_token.get(token)
        elif id is not None:
            return self._by_id.get(id)
        elif name is not None:
            return self._by_name.get(make_safe_name(name))
        return None

    @error_catcher
    async def get_sql(
        self,
        id: int | None = None,
        name: str | None = None,
    ) -> Player | None:
        """Get a player by token, id, or name from sql."""
        # try to get from sql.
        player = await users_repo.fetch_one(
            id=id,
            name=name,
            fetch_all_fields=True,
        )
        if player is None:
            return None

        clan_id: int | None = None
        clan_priv: ClanPrivileges | None = None
        if player["clan_id"] != 0:
            clan_id = player["clan_id"]
            clan_priv = ClanPrivileges(player["clan_priv"])

        return Player(
            id=player["id"],
            name=player["name"],
            priv=Privileges(player["priv"]),
            pw_bcrypt=player["pw_bcrypt"].encode(),
            token=Player.generate_token(),
            clan_id=clan_id,
            clan_priv=clan_priv,
            geoloc={
                "latitude": 0.0,
                "longitude": 0.0,
                "country": {
                    "acronym": player["country"],
                    "numeric": app.state.services.country_codes[player["country"].lower()], # Fix API erroring due to uppercase country codes with .lower()
                },
            },
            silence_end=player["silence_end"],
            donor_end=player["donor_end"],
            api_key=player["api_key"],
        )

    @error_catcher
    async def from_cache_or_sql(
        self,
        id: int | None = None,
        name: str | None = None,
    ) -> Player | None:
        """Try to get player from cache, or sql as fallback."""
        player = self.get(id=id, name=name)
        if player is not None:
            return player
        player = await self.get_sql(id=id, name=name)
        if player is not None:
            return player

        return None

    @error_catcher
    async def from_login(
        self,
        name: str,
        pw_md5: str,
        sql: bool = False,
    ) -> Player | None:
        """Return a player with a given name & pw_md5, from cache or sql."""
        player = self.get(name=name)
        if not player:
            if not sql:
                return None

            player = await self.get_sql(name=name)
            if not player:
                return None

        assert player.pw_bcrypt is not None

        if app.state.cache.bcrypt[player.pw_bcrypt] == pw_md5.encode():
            return player

        return None

    @error_catcher
    def append(self, player: Player) -> None:
        """Append `player` to the list."""
        if player in self:
            if app.settings.DEBUG_LEVEL >= 1:
                log(f"{player} double-added to global player list?")
            return

        super().append(player)
        self._by_token[player.token] = player
        self._by_id[player.id] = player
        self._by_name[player.safe_name] = player

    @error_catcher
    def remove(self, player: Player) -> None:
        """Remove `player` from the list."""
        if player not in self:
            if app.settings.DEBUG_LEVEL >= 1:
                log(f"{player} removed from player list when not online?")
            return

        super().remove(player)
        del self._by_token[player.token]
        del self._by_id[player.id]
        del self._by_name[player.safe_name]


@error_catcher
async def initialize_ram_caches() -> None:
    """Setup & cache the global collections before listening for connections."""
    # fetch channels, clans and pools from db
    await app.state.sessions.channels.prepare()

    bot = await users_repo.fetch_one(id=1)
    if bot is None:
        raise RuntimeError("Bot account not found in database.")

    # create bot & add it to online players
    app.state.sessions.bot = Player(
        id=1,
        name=bot["name"],
        priv=Privileges.UNRESTRICTED,
        pw_bcrypt=None,
        token=Player.generate_token(),
        login_time=float(0x7FFFFFFF),  # (never auto-dc)
        is_bot_client=True,
    )
    app.state.sessions.players.append(app.state.sessions.bot)

    # static api keys
    app.state.sessions.api_keys = {
        row["api_key"]: row["id"]
        for row in (await app.state.services.database.fetch_all(
            "SELECT id, api_key FROM users WHERE api_key IS NOT NULL",
        ) or [])
    }
