"""
Player Module - osu! Player Data Model and Management

This module defines the Player class, which represents a player in the osu! server
application. The Player class is the central data model for user management,
handling all aspects of player state including authentication, privileges, social
interactions, gameplay statistics, and real-time communication.

The Player class manages the complete lifecycle of player sessions from login to
logout, including privilege management, social features (friends, blocks, clans),
multiplayer participation, spectator mode, and packet-based communication with
the osu! client. It integrates with multiple subsystems to provide a comprehensive
player experience.

Key Features:
    - Complete player session management with token-based authentication
    - Hierarchical privilege system with dynamic updates
    - Social features including friends, blocks, and clan membership
    - Multiplayer match participation and management
    - Spectator mode with real-time updates
    - Channel-based communication system
    - Gameplay statistics tracking across all modes
    - Anti-cheat integration with client validation
    - Real-time packet queue management
    - Administrative actions (restrict, silence, etc.)

Integration Points:
    - Authentication in app/api/domains/cho.py
    - Privilege management in app/constants/privileges.py
    - Social features in app/repositories/users.py
    - Multiplayer in app/objects/match.py
    - Spectator mode in app/objects/channel.py
    - Statistics in app/repositories/stats.py
    - Anti-cheat in app/constants/clientflags.py
    - Packet handling in app/packets.py

Player States:
    - Online/Offline: Token-based session tracking
    - Restricted/Unrestricted: Privilege-based access control
    - Silenced/Unsilenced: Communication restrictions
    - In Match/Spectating: Gameplay participation states
    - Bot/Tourney Client: Special client types

Privilege System:
    - Server privileges: Administrative and moderation permissions
    - Client privileges: Client-side permission display
    - Clan privileges: Clan-specific permissions
    - Dynamic privilege updates with client notification

Social Features:
    - Friends list with relationship management
    - Block list for communication filtering
    - Clan membership with role-based permissions
    - Direct messaging and channel communication

Multiplayer Integration:
    - Match joining and leaving with validation
    - Slot management and team assignment
    - Host transfer and referee capabilities
    - Match state synchronization

Spectator System:
    - Spectator channel management
    - Real-time spectator updates
    - Stealth mode for administrative observation
    - Spectator list maintenance

Usage Pattern:
    # Create player instance
    player = Player(
        id=12345,
        name="PlayerName",
        priv=Privileges.UNRESTRICTED,
        pw_bcrypt=hashed_password,
        token=Player.generate_token()
    )

    # Handle player actions
    player.join_match(match, password)
    player.add_spectator(other_player)
    player.enqueue(packet_data)

    # Administrative actions
    await player.restrict(admin, "Reason")
    await player.silence(admin, duration, "Reason")

Related Files:
    - app/api/domains/cho.py: Client connection handling
    - app/objects/match.py: Multiplayer match management
    - app/objects/channel.py: Channel communication
    - app/packets.py: Packet creation and handling
    - app/repositories/users.py: Database operations for players
    - app/repositories/stats.py: Statistics management
"""

from __future__ import annotations

from typing import Callable, Protocol
import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import date
from enum import IntEnum, StrEnum, unique
from functools import cached_property
from typing import TYPE_CHECKING, TypedDict, cast, overload

import app.packets
import app.settings
import app.state
from app._typing import IPAddress
from app.constants.aeris_features import AerisFeatures
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import ClientPrivileges, Privileges
from app.discord import Webhook
from app.logging import Ansi, log, logLevel
from app.objects.channel import Channel
from app.objects.match import Match, MatchTeams, MatchTeamTypes, Slot, SlotStatus
from app.objects.score import Grade, Score
from app.repositories import clans as clans_repo
from app.repositories import logs as logs_repo
from app.repositories import seasons as seasons_repo
from app.repositories import stats as stats_repo
from app.repositories import users as users_repo
from app.state.services import Geolocation
from app.utils import escape_enum, make_safe_name, pymysql_encode

if TYPE_CHECKING:
    from app.constants.privileges import ClanPrivileges
    from app.objects.beatmap import Beatmap
    from app.objects.score import Score


@unique
@pymysql_encode(escape_enum)
class PresenceFilter(IntEnum):
    """osu! client side filter for which users the player can see."""

    Nil = 0
    All = 1
    Friends = 2


@unique
@pymysql_encode(escape_enum)
class Action(IntEnum):
    """The client's current app.state."""

    Idle = 0
    Afk = 1
    Playing = 2
    Editing = 3
    Modding = 4
    Multiplayer = 5
    Watching = 6
    Unknown = 7
    Testing = 8
    Submitting = 9
    Paused = 10
    Lobby = 11
    Multiplaying = 12
    OsuDirect = 13


@dataclass
class ModeData:
    """A player's stats in a single gamemode."""

    tscore: int
    rscore: int
    pp: int
    acc: float
    plays: int
    playtime: int
    max_combo: int
    total_hits: int
    rank: int  # global

    grades: dict[Grade, int]  # XH, X, SH, S, A


@dataclass
class Status:
    """The current status of a player."""

    action: Action = Action.Idle
    info_text: str = ""
    map_md5: str = ""
    mods: Mods = Mods.NOMOD
    mode: GameMode = GameMode.VANILLA_OSU
    map_id: int = 0


class LastNp(TypedDict):
    bmap: Beatmap
    mode_vn: int
    mods: Mods | None
    timeout: float


class OsuStream(StrEnum):
    STABLE = "stable"
    BETA = "beta"
    CUTTINGEDGE = "cuttingedge"
    TOURNEY = "tourney"
    DEV = "dev"
    AERIS = "Aeris"


class OsuVersion:
    # b20200201.2cuttingedge
    # date = 2020/02/01
    # revision = 2
    # stream = cuttingedge
    def __init__(
        self,
        date: date,
        revision: int | None,  # TODO: should this be optional?
        stream: OsuStream,
    ) -> None:
        self.date = date
        self.revision = revision
        self.stream = stream


class ClientDetails:
    def __init__(
        self,
        osu_version: OsuVersion,
        osu_path_md5: str,
        adapters_md5: str,
        uninstall_md5: str,
        disk_signature_md5: str,
        adapters: list[str],
        ip: IPAddress,
    ) -> None:
        self.osu_version = osu_version
        self.osu_path_md5 = osu_path_md5
        self.adapters_md5 = adapters_md5
        self.uninstall_md5 = uninstall_md5
        self.disk_signature_md5 = disk_signature_md5

        self.adapters = adapters
        self.ip = ip

    @cached_property
    def client_hash(self) -> str:
        return (
            # NOTE the extra '.' and ':' appended to ends
            f"{self.osu_path_md5}:{'.'.join(self.adapters)}."
            f":{self.adapters_md5}:{self.uninstall_md5}:{self.disk_signature_md5}:"
        )

    # TODO: __str__ to pack like osu! hashes?


class Player:
    """\
    Server side representation of a player; not necessarily online.

    Possibly confusing attributes
    -----------
    token: `str`
        The player's unique token; used to
        communicate with the osu! client.

    safe_name: `str`
        The player's username (safe).
        XXX: Equivalent to `cls.name.lower().replace(' ', '_')`.

    pm_private: `bool`
        Whether the player is blocking pms from non-friends.

    silence_end: `int`
        The UNIX timestamp the player's silence will end at.

    pres_filter: `PresenceFilter`
        The scope of users the client can currently see.

    is_bot_client: `bool`
        Whether this is a bot account.

    is_tourney_client: `bool`
        Whether this is a management/spectator tourney client.

    _packet_queue: `list[bytes]`
        Bytes enqueued to the player which will be transmitted
        at the tail end of their next connection to the server.
        XXX: cls.enqueue() will add data to this queue, and
             cls.dequeue() will return the data, and remove it.
    """

    def __init__(
        self,
        id: int,
        name: str,
        priv: Privileges,
        pw_bcrypt: bytes | None,
        token: str,
        clan_id: int | None = None,
        clan_priv: ClanPrivileges | None = None,
        clan: clans_repo.Clan | None = None,
        geoloc: Geolocation | None = None,
        utc_offset: int = 0,
        pm_private: bool = False,
        silence_end: int = 0,
        donor_end: int = 0,
        client_details: ClientDetails | None = None,
        login_time: float = 0.0,
        is_bot_client: bool = False,
        is_tourney_client: bool = False,
        api_key: str | None = None,
        preferred_lb_view: str = "all_time",
        selected_season_id: int | None = None,
        preferred_schedule_id: int | None = None,
    ) -> None:
        if geoloc is None:
            geoloc = {
                "latitude": 0.0,
                "longitude": 0.0,
                "country": {"acronym": "xx", "numeric": 0},
            }

        self.id = id
        self.name = name
        self.aeris_client: bool = (
            False  # Identified by the Specific packet dedicated to Kawata/Aeris clients
        )
        self.aeris_client_features: int = AerisFeatures.None_  # by default the client don't take into account any Kawata/Aeris features, because it's another client
        self.priv = priv
        self.pw_bcrypt = pw_bcrypt
        self.token = token
        self.clan_id = clan_id
        self.clan_priv = clan_priv
        self.clan = clan
        self.geoloc = geoloc
        self.utc_offset = utc_offset
        self.pm_private = pm_private
        self.silence_end = silence_end
        self.donor_end = donor_end
        self.client_details = client_details
        self.login_time = login_time
        self.last_recv_time = login_time
        self.is_bot_client = is_bot_client
        self.is_tourney_client = is_tourney_client
        self.api_key = api_key
        self.preferred_lb_view = preferred_lb_view
        self.preferred_schedule_id = preferred_schedule_id
        self.selected_season_id = selected_season_id

        self.away_msg: str | None = None
        self.in_lobby = False

        self.stats: dict[GameMode, ModeData] = {}
        self.season_stats: dict[
            int,
            dict[GameMode, ModeData],
        ] = {}  # season_id -> {mode -> stats}
        self._active_season_by_schedule: dict[
            int,
            int | None,
        ] = {}  # schedule_id -> active season_id cache
        self.status = Status()

        # userids, not player objects
        self.friends: set[int] = set()
        self.blocks: set[int] = set()

        self.channels: list[Channel] = []
        self.spectators: list[Player] = []
        self.spectating: Player | None = None
        self.match: Match | None = None
        self.stealth = False

        self.pres_filter = PresenceFilter.Nil

        # store most recent score for each gamemode.
        self.recent_scores: dict[GameMode, Score | None] = dict.fromkeys(GameMode)

        # store the last beatmap /np'ed by the user.
        self.last_np: LastNp | None = None

        self._packet_queue: list[bytes] = []

    def get_season_stats(self, season_id: int, mode: GameMode) -> ModeData | None:
        """Get stats for a specific season and mode."""
        return self.season_stats.get(season_id, {}).get(mode)

    def get_season_stats_by_schedule(
        self,
        schedule_id: int,
        mode: GameMode,
    ) -> ModeData | None:
        """Get stats for the active season of a specific schedule and mode.

        This method looks up the active season for the given schedule_id
        and returns the stats for that season.
        """
        # This requires async lookup, so we'll need to handle this differently
        # For now, return None - this will be handled in the score submission logic
        return None

    def set_season_stats(self, season_id: int, mode: GameMode, stats: ModeData) -> None:
        """Set stats for a specific season and mode."""
        if season_id not in self.season_stats:
            self.season_stats[season_id] = {}
        self.season_stats[season_id][mode] = stats

    async def load_season_stats(self) -> None:
        """Load stats for all active seasons."""
        try:
            seasons_enabled = await app.state.services.database.fetch_val(
                "SELECT value FROM server_data WHERE type = 'seasons_enabled'",
            )
            if seasons_enabled != "1":
                return

            # Get all active seasons
            active_seasons = await seasons_repo.fetch_many()
            for season in active_seasons:
                if season["is_active"]:
                    # Cache active season by schedule_id for synchronous lookup
                    schedule_id = season.get("schedule_id")
                    if schedule_id is not None:
                        self._active_season_by_schedule[schedule_id] = season["id"]

                    for mode in GameMode:
                        stat = await stats_repo.fetch_one(
                            player_id=self.id,
                            mode=mode.value,
                            season_id=season["id"],
                        )
                        if stat:
                            # Convert Stat TypedDict to ModeData dataclass
                            mode_data = ModeData(
                                tscore=stat["tscore"],
                                rscore=stat["rscore"],
                                pp=stat["pp"],
                                acc=stat["acc"],
                                plays=stat["plays"],
                                playtime=stat["playtime"],
                                max_combo=stat["max_combo"],
                                total_hits=stat["total_hits"],
                                rank=0,
                                grades={
                                    Grade.XH: stat["xh_count"],
                                    Grade.X: stat["x_count"],
                                    Grade.SH: stat["sh_count"],
                                    Grade.S: stat["s_count"],
                                    Grade.A: stat["a_count"],
                                },
                            )
                            # Set stats first so update_season_rank can read them
                            self.set_season_stats(season["id"], mode, mode_data)
                            await self.update_season_rank(season["id"], mode)
                            mode_data.rank = await self.get_season_rank(season["id"], mode)
        except Exception as e:
            log(
                f"Failed to load season stats for {self}: {e}",
                Ansi.LRED,
                level=logLevel.ERROR,
            )

    def get_active_season_for_schedule(self, schedule_id: int) -> int | None:
        """Get the active season ID for a specific schedule.

        Returns the cached active season ID for the given schedule.
        The cache is populated during load_season_stats().

        Returns:
            The season_id of the active season for the given schedule, or None if no active season.
        """
        return self._active_season_by_schedule.get(schedule_id)

    def __repr__(self) -> str:
        return f"<{self.name} ({self.id})>"

    @property
    def safe_name(self) -> str:
        return make_safe_name(self.name)

    @property
    def is_online(self) -> bool:
        return bool(self.token != "")

    @property
    def url(self) -> str:
        """The url to the player's profile."""
        return f"https://{app.settings.DOMAIN}/u/{self.id}"

    @property
    def embed(self) -> str:
        """An osu! chat embed to the player's profile."""
        return f"[{self.url} {self.name}]"

    @property
    def avatar_url(self) -> str:
        """The url to the player's avatar."""
        return f"https://a.{app.settings.DOMAIN}/{self.id}"

    # TODO: chat embed with clan tag hyperlinked?

    @property
    def remaining_silence(self) -> int:
        """The remaining time of the players silence."""
        return max(0, int(self.silence_end - time.time()))

    @property
    def silenced(self) -> bool:
        """Whether or not the player is silenced."""
        return self.remaining_silence != 0

    @cached_property
    def bancho_priv(self) -> ClientPrivileges:
        """The player's privileges according to the client."""
        ret = ClientPrivileges(0)
        if self.priv & Privileges.UNRESTRICTED:
            ret |= ClientPrivileges.PLAYER
        if self.priv & Privileges.DONATOR:
            ret |= ClientPrivileges.SUPPORTER
        if self.priv & Privileges.MODERATOR:
            ret |= ClientPrivileges.MODERATOR
        if self.priv & Privileges.ADMINISTRATOR:
            ret |= ClientPrivileges.DEVELOPER
        if self.priv & Privileges.DEVELOPER:
            ret |= ClientPrivileges.OWNER
        return ret

    @property
    def restricted(self) -> bool:
        """Return whether the player is restricted."""
        return not self.priv & Privileges.UNRESTRICTED

    @property
    def gm_stats(self) -> ModeData:
        """The player's stats in their currently selected mode.

        Returns seasonal stats if the player has preferred_lb_view set to 'seasonal'
        and has a selected_season_id, otherwise returns all-time stats.
        """
        if self.preferred_lb_view == "seasonal":
            if self.selected_season_id is not None:
                season_stats = self.get_season_stats(
                    self.selected_season_id,
                    self.status.mode,
                )
            else:
                schedule_id: int = 0
                season_id: int = 0
                if self.preferred_schedule_id is not None:
                    schedule_id = self.preferred_schedule_id
                if schedule_id != 0:
                    season_id = self.get_active_season_for_schedule(schedule_id) or 0
                else:
                    # No schedule specified, try to get the first active season
                    # from any schedule as a default
                    for sched_id, s_id in self._active_season_by_schedule.items():
                        if s_id is not None:
                            schedule_id = sched_id
                            season_id = s_id
                            break
                if season_id != 0:
                    season_stats = self.get_season_stats(season_id, self.status.mode)
                else:
                    season_stats = None
            if season_stats is not None:
                return season_stats
        return self.stats[self.status.mode]

    @property
    def recent_score(self) -> Score | None:
        """The player's most recently submitted score."""
        score = None
        for s in self.recent_scores.values():
            if not s:
                continue

            if not score:
                score = s
                continue

            if s.server_time > score.server_time:
                score = s

        return score

    @property
    def has_group_capability(self) -> bool:
        """Does the server and the client has group capabilities"""
        from app.api.domains.packets.aeris import AERIS_SERVER_FEATURES

        return (
            self.aeris_client
            and AERIS_SERVER_FEATURES & AerisFeatures.Groups > 0
            and self.aeris_client_features & AerisFeatures.Groups > 0
        )

    @staticmethod
    def generate_token() -> str:
        """Generate a random uuid as a token."""
        return str(uuid.uuid4())

    def logout(self) -> None:
        """Log `self` out of the server."""
        # Store the token before clearing it (needed for removal from _by_token)
        original_token = self.token

        # invalidate the user's token.
        self.token = ""

        # leave multiplayer.
        if self.match:
            self.leave_match()

        group = app.state.sessions.groups.get_group(self)
        if group is not None:
            if group.lead is self:
                group.disband()
            else:
                group.remove_user(self)

        # stop spectating.
        host = self.spectating
        if host:
            host.remove_spectator(self)

        # leave channels
        while self.channels:
            self.leave_channel(self.channels[0], kick=False)

        # remove from playerlist and
        # enqueue logout to all users.
        app.state.sessions.players.remove(self, original_token=original_token)

        if not self.restricted:
            if app.state.services.datadog:
                app.state.services.datadog.decrement("bancho.online_players")  # type: ignore[no-untyped-call]

            app.state.sessions.players.enqueue(app.packets.logout(self.id))

        log(f"{self} logged out.")

    async def update_privs(self, new: Privileges) -> None:
        """Update `self`'s privileges to `new`."""

        self.priv = new
        if "bancho_priv" in vars(self):
            del self.bancho_priv  # wipe cached_property

        await users_repo.partial_update(
            id=self.id,
            priv=self.priv,
        )

    async def add_privs(self, bits: Privileges) -> None:
        """Update `self`'s privileges, adding `bits`."""

        self.priv |= bits
        if "bancho_priv" in vars(self):
            del self.bancho_priv  # wipe cached_property

        await users_repo.partial_update(
            id=self.id,
            priv=self.priv,
        )

        if self.is_online:
            # if they're online, send a packet
            # to update their client-side privileges
            self.enqueue(app.packets.bancho_privileges(self.bancho_priv))

    async def remove_privs(self, bits: Privileges) -> None:
        """Update `self`'s privileges, removing `bits`."""

        self.priv &= ~bits
        if "bancho_priv" in vars(self):
            del self.bancho_priv  # wipe cached_property

        await users_repo.partial_update(
            id=self.id,
            priv=self.priv,
        )

        if self.is_online:
            # if they're online, send a packet
            # to update their client-side privileges
            self.enqueue(app.packets.bancho_privileges(self.bancho_priv))

    async def restrict(self, admin: Player, reason: str) -> None:
        """Restrict `self` for `reason`, and log to sql."""
        await self.remove_privs(Privileges.UNRESTRICTED)

        await logs_repo.create(
            from_id=admin.id,
            to_id=self.id,
            action="restrict",
            msg=reason,
        )

        for mode in (0, 1, 2, 3, 4, 5, 6, 8):
            await app.state.services.redis.zrem(
                f"bancho:leaderboard:{mode}",
                self.id,
            )
            await app.state.services.redis.zrem(
                f"bancho:leaderboard:{mode}:{self.geoloc['country']['acronym']}",
                self.id,
            )

        log_msg = f"{admin} restricted {self} for: {reason}."

        log(log_msg, Ansi.LRED, level=logLevel.INFO)

        webhook_url = app.settings.DISCORD_AUDIT_LOG_WEBHOOK
        if webhook_url:
            webhook = Webhook(webhook_url, content=log_msg)
            asyncio.create_task(webhook.post())  # type: ignore[unused-awaitable]

        # refresh their client state
        if self.is_online:
            self.logout()

    async def unrestrict(self, admin: Player, reason: str) -> None:
        """Restrict `self` for `reason`, and log to sql."""
        await self.add_privs(Privileges.UNRESTRICTED)

        await logs_repo.create(
            from_id=admin.id,
            to_id=self.id,
            action="unrestrict",
            msg=reason,
        )

        if not self.is_online:
            await self.stats_from_sql_full()
            await self.load_season_stats()

        for mode, stats in self.stats.items():
            if stats.pp <= 0 and stats.plays == 0:
                continue  # skip unplayed modes to avoid polluting leaderboards
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode.value}",
                {str(self.id): stats.pp},
            )
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode.value}:{self.geoloc['country']['acronym']}",
                {str(self.id): stats.pp},
            )

        log_msg = f"{admin} unrestricted {self} for: {reason}."

        log(log_msg, Ansi.LRED)

        webhook_url = app.settings.DISCORD_AUDIT_LOG_WEBHOOK
        if webhook_url:
            webhook = Webhook(webhook_url, content=log_msg)
            asyncio.create_task(webhook.post())  # type: ignore[unused-awaitable]

        if self.is_online:
            # log the user out if they're offline, this
            # will simply relog them and refresh their app.state
            self.logout()

    async def silence(self, admin: Player, duration: float, reason: str) -> None:
        """Silence `self` for `duration` seconds, and log to sql."""
        self.silence_end = int(time.time() + duration)

        await users_repo.partial_update(
            id=self.id,
            silence_end=self.silence_end,
        )

        await logs_repo.create(
            from_id=admin.id,
            to_id=self.id,
            action="silence",
            msg=reason,
        )

        # inform the user's client.
        self.enqueue(app.packets.silence_end(int(duration)))

        # wipe their messages from any channels.
        app.state.sessions.players.enqueue(app.packets.user_silenced(self.id))

        # remove them from multiplayer match (if any).
        if self.match:
            self.leave_match()

        log(f"Silenced {self}.", Ansi.LCYAN)

    async def unsilence(self, admin: Player, reason: str) -> None:
        """Unsilence `self`, and log to sql."""
        self.silence_end = int(time.time())

        await users_repo.partial_update(
            id=self.id,
            silence_end=self.silence_end,
        )

        await logs_repo.create(
            from_id=admin.id,
            to_id=self.id,
            action="unsilence",
            msg=reason,
        )

        # inform the user's client
        self.enqueue(app.packets.silence_end(0))

        log(f"Unsilenced {self}.", Ansi.LCYAN)

    def join_match(self, match: Match, passwd: str) -> bool:
        """Attempt to add `self` to `match`."""
        if self.match:
            log(f"{self} tried to join multiple matches?")
            self.enqueue(app.packets.match_join_fail())
            return False

        if self.id in match.tourney_clients:
            # the user is already in the match with a tourney client.
            # users cannot spectate themselves so this is not possible.
            self.enqueue(app.packets.match_join_fail())
            return False

        if self is not match.host:
            # match already exists, we're simply joining.
            # NOTE: staff members have override to pw and can
            # simply use any to join a pw protected match.
            if passwd != match.passwd and self not in app.state.sessions.players.staff:
                log(f"{self} tried to join {match} w/ incorrect pw.", Ansi.LYELLOW)
                self.enqueue(app.packets.match_join_fail())
                return False
            slot_id = match.get_free()
            if slot_id is None:
                log(f"{self} tried to join a full match.", Ansi.LYELLOW)
                self.enqueue(app.packets.match_join_fail())
                return False

        else:
            # match is being created
            slot_id = 0

        if not self.join_channel(match.chat):
            log(f"{self} failed to join {match.chat}.", Ansi.LYELLOW)
            return False

        lobby = app.state.sessions.channels.get_by_name("#lobby")
        if lobby in self.channels:
            self.leave_channel(lobby)

        slot: Slot = match.slots[0 if slot_id == -1 else slot_id]

        # if in a teams-vs mode, switch team from neutral to red.
        if match.team_type in (MatchTeamTypes.team_vs, MatchTeamTypes.tag_team_vs):
            slot.team = MatchTeams.red

        slot.status = SlotStatus.not_ready
        slot.player = self
        self.match = match

        self.enqueue(app.packets.match_join_success(match))
        match.enqueue_state()

        return True

    def leave_match(self) -> None:
        """Attempt to remove `self` from their match."""
        if not self.match:
            if app.settings.DEBUG_LEVEL >= 1:
                log(f"{self} tried leaving a match they're not in?", Ansi.LYELLOW)
            return

        slot = self.match.get_slot(self)
        assert slot is not None

        if slot.status == SlotStatus.locked:
            # player was kicked, keep the slot locked.
            new_status = SlotStatus.locked
        else:
            # player left, open the slot for new players to join.
            new_status = SlotStatus.open

        slot.reset(new_status=new_status)

        self.leave_channel(self.match.chat)

        if all(s.empty() for s in self.match.slots):
            # multi is now empty, chat has been removed.
            # remove the multi from the channels list.
            log(f"Match {self.match} finished.")

            # cancel any pending start timers
            if self.match.starting is not None:
                self.match.starting["start"].cancel()
                for alert in self.match.starting["alerts"]:
                    alert.cancel()

                self.match.starting = None

            app.state.sessions.matches.remove(self.match)

            lobby = app.state.sessions.channels.get_by_name("#lobby")
            if lobby:
                lobby.enqueue(app.packets.dispose_match(self.match.id))

        else:  # multi is not empty
            if self is self.match.host:
                # player was host, trasnfer to first occupied slot
                for s in self.match.slots:
                    if s.player is not None:
                        self.match.host_id = s.player.id
                        self.match.host.enqueue(app.packets.match_transfer_host())
                        break

            if self in self.match.referees:
                self.match.referees.remove(self)
                self.match.chat.send_bot(f"{self.name} removed from match referees.")

            # notify others of our deprature
            self.match.enqueue_state()

        self.match = None

    def join_channel(self, channel: Channel) -> bool:
        """Attempt to add `self` to `channel`."""
        if (
            self in channel
            or not channel.can_read(self.priv)  # player already in channel
            or channel.real_name == "#lobby"  # no read privs
            and not self.in_lobby  # not in mp lobby
        ):
            return False

        channel.append(self)  # add to channel.players
        self.channels.append(channel)  # add to player.channels

        self.enqueue(app.packets.channel_join(channel.name))

        chan_info_packet = app.packets.channel_info(
            channel.name,
            channel.topic,
            len(channel.players),
        )

        if channel.instance:
            # instanced channel, only send the players
            # who are currently inside the instance
            for player in channel.players:
                player.enqueue(chan_info_packet)
        else:
            # normal channel, send to all players who
            # have access to see the channel's usercount.
            for player in app.state.sessions.players:
                if channel.can_read(player.priv):
                    player.enqueue(chan_info_packet)

        if app.settings.DEBUG_LEVEL >= 1:
            log(f"{self} joined {channel}.")

        return True

    def leave_channel(self, channel: Channel, kick: bool = True) -> None:
        """Attempt to remove `self` from `channel`."""
        # ensure they're in the chan.
        if self not in channel:
            return

        channel.remove(self)  # remove from c.players
        self.channels.remove(channel)  # remove from player.channels

        if kick:
            self.enqueue(app.packets.channel_kick(channel.name))

        chan_info_packet = app.packets.channel_info(
            channel.name,
            channel.topic,
            len(channel.players),
        )

        if channel.instance:
            # instanced channel, only send the players
            # who are currently inside the instance
            for player in channel.players:
                player.enqueue(chan_info_packet)
        else:
            # normal channel, send to all players who
            # have access to see the channel's usercount.
            for player in app.state.sessions.players:
                if channel.can_read(player.priv):
                    player.enqueue(chan_info_packet)

        if app.settings.DEBUG_LEVEL >= 1:
            log(f"{self} left {channel}.")

    def add_spectator(self, player: Player) -> None:
        """Attempt to add `player` to `self`'s spectators."""
        chan_name = f"#spec_{self.id}"

        spec_chan = app.state.sessions.channels.get_by_name(chan_name)
        if not spec_chan:
            # spectator chan doesn't exist, create it.
            spec_chan = Channel(
                name=chan_name,
                topic=f"{self.name}'s spectator channel.",
                auto_join=False,
                instance=True,
            )

            self.join_channel(spec_chan)
            app.state.sessions.channels.append(spec_chan)

        # attempt to join their spectator channel.
        if not player.join_channel(spec_chan):
            log(f"{self} failed to join {spec_chan}?", Ansi.LYELLOW)
            return

        if not player.stealth:
            player_joined = app.packets.fellow_spectator_joined(player.id)
            for spectator in self.spectators:
                spectator.enqueue(player_joined)
                player.enqueue(app.packets.fellow_spectator_joined(spectator.id))

            self.enqueue(app.packets.spectator_joined(player.id))
        else:
            # player is admin in stealth, only give
            # other players data to us, not vice-versa.
            for spectator in self.spectators:
                player.enqueue(app.packets.fellow_spectator_joined(spectator.id))

        self.spectators.append(player)
        player.spectating = self

        log(f"{player} is now spectating {self}.")

    def remove_spectator(self, player: Player) -> None:
        """Attempt to remove `player` from `self`'s spectators."""
        self.spectators.remove(player)
        player.spectating = None

        channel = app.state.sessions.channels.get_by_name(f"#spec_{self.id}")
        assert channel is not None

        player.leave_channel(channel)

        if not self.spectators:
            # remove host from channel, deleting it.
            self.leave_channel(channel)
        else:
            # send new playercount
            channel_info = app.packets.channel_info(
                channel.name,
                channel.topic,
                len(channel.players),
            )
            fellow = app.packets.fellow_spectator_left(player.id)

            self.enqueue(channel_info)

            for spectator in self.spectators:
                spectator.enqueue(fellow + channel_info)

        self.enqueue(app.packets.spectator_left(player.id))
        log(f"{player} is no longer spectating {self}.")

    async def add_friend(self, player: Player) -> None:
        """Attempt to add `player` to `self`'s friends."""
        if player.id in self.friends:
            log(
                f"{self} tried to add {player}, who is already their friend!",
                Ansi.LYELLOW,
            )
            return

        self.friends.add(player.id)
        await app.state.services.database.execute(
            "REPLACE INTO relationships (user1, user2, type) VALUES (:user1, :user2, 'friend')",
            {"user1": self.id, "user2": player.id},
        )

        log(f"{self} friended {player}.")

    async def remove_friend(self, player: Player) -> None:
        """Attempt to remove `player` from `self`'s friends."""
        if player.id not in self.friends:
            log(
                f"{self} tried to unfriend {player}, who is not their friend!",
                Ansi.LYELLOW,
            )
            return

        self.friends.remove(player.id)
        await app.state.services.database.execute(
            "DELETE FROM relationships WHERE user1 = :user1 AND user2 = :user2",
            {"user1": self.id, "user2": player.id},
        )

        log(f"{self} unfriended {player}.")

    async def add_block(self, player: Player) -> None:
        """Attempt to add `player` to `self`'s blocks."""
        if player.id in self.blocks:
            log(
                f"{self} tried to block {player}, who they've already blocked!",
                Ansi.LYELLOW,
            )
            return

        self.blocks.add(player.id)
        await app.state.services.database.execute(
            "REPLACE INTO relationships VALUES (:user1, :user2, 'block')",
            {"user1": self.id, "user2": player.id},
        )

        log(f"{self} blocked {player}.")

    async def remove_block(self, player: Player) -> None:
        """Attempt to remove `player` from `self`'s blocks."""
        if player.id not in self.blocks:
            log(
                f"{self} tried to unblock {player}, who they haven't blocked!",
                Ansi.LYELLOW,
            )
            return

        self.blocks.remove(player.id)
        await app.state.services.database.execute(
            "DELETE FROM relationships WHERE user1 = :user1 AND user2 = :user2",
            {"user1": self.id, "user2": player.id},
        )

        log(f"{self} unblocked {player}.")

    async def relationships_from_sql(self) -> None:
        """Retrieve `self`'s relationships from sql."""
        for row in (
            await app.state.services.database.fetch_all(
                "SELECT user2, type FROM relationships WHERE user1 = :user1",
                {"user1": self.id},
            )
            or []
        ):
            if row["type"] == "friend":
                self.friends.add(row["user2"])
            else:
                self.blocks.add(row["user2"])

        # always have bot added to friends.
        self.friends.add(1)

    async def get_global_rank(self, mode: GameMode) -> int:
        if self.restricted:
            return 0

        rank = await app.state.services.redis.zrevrank(
            f"bancho:leaderboard:{mode.value}",
            str(self.id),
        )
        return cast(int, rank) + 1 if rank is not None else 0

    async def get_season_rank(self, season_id: int, mode: GameMode) -> int:
        """Get the player's rank in a specific season and mode."""
        if self.restricted:
            return 0

        rank = await app.state.services.redis.zrevrank(
            f"bancho:leaderboard:{mode.value}:season:{season_id}",
            str(self.id),
        )
        return cast(int, rank) + 1 if rank is not None else 0

    async def get_country_rank(self, mode: GameMode) -> int:
        if self.restricted:
            return 0

        country = self.geoloc["country"]["acronym"]
        rank = await app.state.services.redis.zrevrank(
            f"bancho:leaderboard:{mode.value}:{country}",
            str(self.id),
        )

        return cast(int, rank) + 1 if rank is not None else 0

    async def update_rank(self, mode: GameMode) -> int:
        country = self.geoloc["country"]["acronym"]
        stats = self.stats[mode]

        if not self.restricted:
            # global rank
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode.value}",
                {str(self.id): stats.pp},
            )

            # country rank
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode.value}:{country}",
                {str(self.id): stats.pp},
            )

        return await self.get_global_rank(mode)

    async def update_season_rank(self, season_id: int, mode: GameMode) -> int:
        """Update the player's rank in a specific season and mode.

        Returns the player's rank after the update.
        """
        season_stats = self.get_season_stats(season_id, mode)
        if season_stats is None:
            return 0

        if not self.restricted:
            # Update season leaderboard
            await app.state.services.redis.zadd(
                f"bancho:leaderboard:{mode.value}:season:{season_id}",
                {str(self.id): season_stats.pp},
            )

        return await self.get_season_rank(season_id, mode)

    async def stats_from_sql_full(self) -> None:
        """Retrieve `self`'s stats (all modes) from sql."""
        # Initialize empty stats for all game modes to prevent KeyError
        for mode in GameMode:
            if mode not in self.stats:
                self.stats[mode] = ModeData(
                    tscore=0,
                    rscore=0,
                    pp=0,
                    acc=0.0,
                    plays=0,
                    playtime=0,
                    max_combo=0,
                    total_hits=0,
                    rank=0,
                    grades={
                        Grade.XH: 0,
                        Grade.X: 0,
                        Grade.SH: 0,
                        Grade.S: 0,
                        Grade.A: 0,
                    },
                )

        # Then load from database
        for row in await stats_repo.fetch_many(player_id=self.id):
            game_mode = GameMode(row["mode"])
            self.stats[game_mode] = ModeData(
                tscore=row["tscore"],
                rscore=row["rscore"],
                pp=row["pp"],
                acc=row["acc"],
                plays=row["plays"],
                playtime=row["playtime"],
                max_combo=row["max_combo"],
                total_hits=row["total_hits"],
                rank=await self.get_global_rank(game_mode),
                grades={
                    Grade.XH: row["xh_count"],
                    Grade.X: row["x_count"],
                    Grade.SH: row["sh_count"],
                    Grade.S: row["s_count"],
                    Grade.A: row["a_count"],
                },
            )

    def update_latest_activity_soon(self) -> None:
        """Update the player's latest activity in the database."""
        task = users_repo.partial_update(
            id=self.id,
            latest_activity=int(time.time()),
        )
        app.state.loop.create_task(task)  # type: ignore[unused-awaitable]

    def enqueue(self, data: bytes) -> None:
        """Add data to be sent to the client."""
        if self.is_bot_client:
            return  # avoid enqueuing packets to bot accounts
        self._packet_queue.append(data)

    def _bot_enqueue(self, data: bytes) -> None:
        """No-op enqueue for bot accounts."""
        pass

    def dequeue(self) -> bytes | None:
        """Get data from the queue to send to the client."""
        if self._packet_queue:
            data = b"".join(self._packet_queue)
            self._packet_queue.clear()
            return data

        return None

    def send(self, msg: str, sender: Player, chan: Channel | None = None) -> None:
        """Enqueue `sender`'s `msg` to `self`. Sent in `chan`, or dm."""
        self.enqueue(
            app.packets.send_message(
                sender=sender.name,
                msg=msg,
                recipient=(chan or self).name,
                sender_id=sender.id,
            ),
        )

    def send_bot(self, msg: str) -> None:
        """Enqueue `msg` to `self` from bot."""
        bot = app.state.sessions.bot

        self.enqueue(
            app.packets.send_message(
                sender=bot.name,
                msg=msg,
                recipient=self.name,
                sender_id=bot.id,
            ),
        )

    async def update_season_preference(self, preference: str) -> None:
        """Update the player's season view preference.

        Args:
            preference: Either "all_time" or "seasonal"
        """
        if preference not in ("all_time", "seasonal"):
            raise ValueError("Preference must be 'all_time' or 'seasonal'")

        self.preferred_lb_view = preference
        await users_repo.partial_update(
            id=self.id,
            preferred_lb_view=preference,
        )
