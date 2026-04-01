"""
Channel Module - osu! Chat Channel Data Model

This module defines the Channel class, which represents an osu! chat channel
for player communication. Channels are fundamental components of the osu! social
system, enabling real-time text communication between players in various contexts
such as public chat, private messages, multiplayer lobbies, and spectator modes.

The Channel class manages player membership, message routing, and access control
based on user privileges. It supports both persistent channels (like #osu) and
temporary instance channels (like multiplayer and spectator rooms) that are
automatically cleaned up when empty.

Key Features:
    - Player membership management with automatic cleanup
    - Privilege-based access control for reading and writing
    - Message routing with block list support
    - Instance channel support for temporary rooms
    - Bot message integration for automated responses
    - Selective message sending to specific recipients
    - Automatic channel name normalization for client compatibility

Integration Points:
    - Player messaging in app/objects/player.py
    - Packet handling in app/packets.py
    - Session management in app/state/sessions.py
    - Privilege checking in app/constants/privileges.py
    - Multiplayer management in app/objects/match.py

Channel Types:
    - Public channels: Persistent channels like #osu, #announce
    - Private channels: Direct messages between players
    - Multiplayer channels: Temporary rooms for multiplayer matches
    - Spectator channels: Temporary rooms for spectating sessions
    - Group channels: Channels for specific player groups

Access Control:
    - read_priv: Minimum privilege required to read messages
    - write_priv: Minimum privilege required to send messages
    - Privilege checking uses bitwise AND operations
    - UNRESTRICTED privilege allows all users to access

Instance Channels:
    - Temporary channels that exist only while players are present
    - Automatically deleted when the last player leaves
    - Used for multiplayer, spectator, and other temporary contexts
    - Identified by special name prefixes (#multi_, #spec_, #group_)

Usage Pattern:
    - Channels are created and managed by the session system
    - Players join channels during connection and gameplay
    - Messages are routed through channels to appropriate recipients
    - Instance channels are cleaned up automatically when empty

Example Usage:
    # Create a channel
    channel = Channel(
        name="#osu",
        topic="General discussion",
        read_priv=Privileges.UNRESTRICTED,
        write_priv=Privileges.UNRESTRICTED
    )

    # Add player to channel
    channel.append(player)

    # Send message to channel
    channel.send("Hello everyone!", sender=player)

    # Check if player can write
    if channel.can_write(player.privileges):
        channel.send("Message", sender=player)

Related Files:
    - app/objects/player.py: Player class with channel interactions
    - app/packets.py: Packet creation for channel messages
    - app/state/sessions.py: Session management with channel tracking
    - app/objects/match.py: Multiplayer match channels
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import app.packets
import app.state
from app.constants.privileges import Privileges

if TYPE_CHECKING:
    from app.objects.player import Player


class Channel:
    """An osu! chat channel.

    Possibly confusing attributes
    -----------
    real_name: `str`
        A name string of the channel.
        The cls.`name` property wraps handling for '#multiplayer' and
        '#spectator' when communicating with the osu! client; only use
        this attr when you need the channel's true name; otherwise you
        should use the `name` property described below.

    instance: `bool`
        Instanced channels are deleted when all players have left;
        this is useful for things like multiplayer, spectator, etc.
    """

    def __init__(
        self,
        name: str,
        topic: str,
        read_priv: Privileges = Privileges.UNRESTRICTED,
        write_priv: Privileges = Privileges.UNRESTRICTED,
        auto_join: bool = True,
        instance: bool = False,
    ) -> None:
        self.real_name = name

        if self.real_name.startswith("#spec_"):
            self.name = "#spectator"
        elif self.real_name.startswith("#multi_"):
            self.name = "#multiplayer"
        elif self.real_name.startswith("#group_"):
            self.name = "#group"
        else:
            self.name = self.real_name

        self.topic = topic
        self.read_priv = read_priv
        self.write_priv = write_priv
        self.auto_join = auto_join
        self.instance = instance

        self.players: list[Player] = []

    def __repr__(self) -> str:
        return f"<{self.real_name}>"

    def __contains__(self, player: Player) -> bool:
        return player in self.players

    # XXX: should this be cached differently?

    def can_read(self, priv: Privileges) -> bool:
        if not self.read_priv:
            return True

        return priv & self.read_priv != 0

    def can_write(self, priv: Privileges) -> bool:
        if not self.write_priv:
            return True

        return priv & self.write_priv != 0

    def send(self, msg: str, sender: Player, to_self: bool = False) -> None:
        """Enqueue `msg` to all appropriate clients from `sender`."""
        data = app.packets.send_message(
            sender=sender.name,
            msg=msg,
            recipient=self.name,
            sender_id=sender.id,
        )

        for player in self.players:
            if sender.id not in player.blocks and (to_self or player.id != sender.id):
                player.enqueue(data)

    def send_bot(self, msg: str) -> None:
        """Enqueue `msg` to all connected clients from bot."""
        bot = app.state.sessions.bot

        msg_len = len(msg)

        if msg_len >= 31979:  # TODO ??????????
            msg = f"message would have crashed games ({msg_len} chars)"

        self.enqueue(
            app.packets.send_message(
                sender=bot.name,
                msg=msg,
                recipient=self.name,
                sender_id=bot.id,
            ),
        )

    def send_selective(
        self,
        msg: str,
        sender: Player,
        recipients: set[Player],
    ) -> None:
        """Enqueue `sender`'s `msg` to `recipients`."""
        for player in recipients:
            if player in self:
                player.send(msg, sender=sender, chan=self)

    def append(self, player: Player) -> None:
        """Add `player` to the channel's players."""
        self.players.append(player)

    def remove(self, player: Player) -> None:
        """Remove `player` from the channel's players."""
        self.players.remove(player)

        if not self.players and self.instance:
            # if it's an instance channel and this
            # is the last member leaving, just remove
            # the channel from the global list.
            app.state.sessions.channels.remove(self)

    def enqueue(self, data: bytes, immune: Sequence[int] = []) -> None:
        """Enqueue `data` to all connected clients not in `immune`."""
        for player in self.players:
            if player.id not in immune:
                player.enqueue(data)
