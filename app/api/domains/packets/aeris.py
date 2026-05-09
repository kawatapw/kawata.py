"""
Aeris Packets Module - Custom Packet Handlers for Aeris Client Features

This module implements custom packet handlers for the Aeris client, which is
an enhanced osu! client that supports additional features beyond the standard
osu! client. The module provides handlers for group management, client
identification, and various Aeris-specific functionality.

The module extends the standard osu! packet handling system with additional
capabilities for group management, client feature detection, and enhanced
multiplayer functionality. It integrates with the server's group management
system and provides a foundation for Aeris-specific features.

Key Features:
    - Aeris client identification and feature detection
    - Group creation and management system
    - Group invitation and membership handling
    - Group-based multiplayer match coordination
    - Client feature flag management
    - Integration with standard osu! packet system

Integration Points:
    - Group management in app/objects/group.py
    - Player management in app/objects/player.py
    - Packet system in app/packets.py
    - Session management in app/state/sessions.py
    - Feature flags in app/constants/aeris_features.py
    - Settings in app/settings.py

Packet Handlers:
    - IDENTIFY: Client identification and feature negotiation
    - CREATE_GROUP: Group creation for multiplayer coordination
    - ACCEPT_GROUP: Group invitation acceptance
    - DISBAND_GROUP: Group dissolution
    - INVITE_GROUP: Group invitation sending
    - GROUP_KICK: Group member removal
    - GROUP_LEAVE: Voluntary group departure
    - GROUP_USERS: Group member list retrieval
    - CREATE_GROUP_MATCH: Group-based match creation (not implemented)
    - DISMOUNT_GROUP_MATCH: Group match dissolution (not implemented)

Group Management Flow:
    1. Player creates a group with CREATE_GROUP packet
    2. Group leader invites players with INVITE_GROUP packet
    3. Invited players accept with ACCEPT_GROUP packet
    4. Group members can leave with GROUP_LEAVE packet
    5. Group leader can kick members with GROUP_KICK packet
    6. Group leader can disband with DISBAND_GROUP packet

Aeris Client Features:
    - Enhanced group management capabilities
    - Custom packet support for advanced features
    - Feature flag negotiation with server
    - Extended multiplayer functionality

Usage Pattern:
    # Client identifies as Aeris client
    IDENTIFY packet with feature flags

    # Create a group
    CREATE_GROUP packet

    # Invite player to group
    INVITE_GROUP packet with target player ID

    # Accept group invitation
    ACCEPT_GROUP packet with leader ID

    # Leave or disband group
    GROUP_LEAVE or DISBAND_GROUP packet

Related Files:
    - app/objects/group.py: Group data model and management
    - app/objects/player.py: Player class with group interactions
    - app/packets.py: Packet definitions and utilities
    - app/state/sessions.py: Session and group management
    - app/constants/aeris_features.py: Aeris feature flag definitions
"""

from __future__ import annotations

import app.settings
from app.constants.aeris_features import AerisFeatures
from app.logging import Ansi
from app.logging import log
from app.objects.group import Group
from app.objects.player import Player
from app.packets import BanchoPacketReader
from app.packets import BasePacket
from app.packets import ClientPackets
from app.state.sessions import groups
from app.state.sessions import players

from .common import register

AERIS_SERVER_FEATURES: int = AerisFeatures.Groups
if app.settings.CHEAT_SERVER:
    AERIS_SERVER_FEATURES |= AerisFeatures.Cheats


@register(ClientPackets.IDENTIFY, restricted=True)
class AerisIdentify(BasePacket):
    """Handle Aeris client identification and feature negotiation.

    This packet handler processes the IDENTIFY packet from Aeris clients,
    which is used to identify the client as an Aeris client and negotiate
    available features between client and server.
    """

    def __init__(self, reader: BanchoPacketReader):
        self.features = reader.read_i32()

    async def handle(self, player: Player) -> None:
        server_features = 0 if player.restricted else AERIS_SERVER_FEATURES
        player.enqueue(app.packets.identify(server_features))
        # This identify an Aeris client from a PPY Client or any other client
        # used primarly to enable serverside features for this client
        log(
            f"user {player.name} ({player.id}) is using an Aeris client with the flags {self.features}",
            Ansi.BLUE,
        )
        player.aeris_client = True
        player.aeris_client_features = self.features


@register(ClientPackets.CREATE_GROUP)
class CreateGroup(BasePacket):
    """Handle group creation requests from Aeris clients.

    This packet handler processes the CREATE_GROUP packet, which is used
    to create a new player group for multiplayer coordination or social
    interaction.
    """

    async def handle(self, player: Player) -> None:
        log(f"user {player.name} ({player.id}) making group", Ansi.BLUE)
        old_group = groups.get_group(player)
        if old_group is not None:
            old_group.remove_user(player)
        Group(player)


@register(ClientPackets.CREATE_GROUP_MATCH)
@register(ClientPackets.DISMOUNT_GROUP_MATCH)
class unavail(BasePacket):
    """Handle group match creation and dissolution requests.

    These packet handlers are placeholders for group-based match
    functionality that is not yet implemented.
    """

    async def handle(self, player: Player) -> None:
        player.enqueue(app.packets.notification("this feature is not yet available"))


@register(ClientPackets.GROUP_USERS)
class GroupUsers(BasePacket):
    """Handle requests for group member information.

    This packet handler processes the GROUP_USERS packet, which is used
    to retrieve the list of players in the current group.
    """

    async def handle(self, player: Player) -> None:
        group = groups.get_group(player)
        if group is not None:
            player.enqueue(app.packets.group_users(player))


@register(ClientPackets.ACCEPT_GROUP)
class acceptGroup(BasePacket):
    """Handle group invitation acceptance.

    This packet handler processes the ACCEPT_GROUP packet, which is used
    when a player accepts an invitation to join a group.
    """

    def __init__(self, reader: BanchoPacketReader) -> None:
        self.lead = players.get(id=reader.read_i32())

    async def handle(self, player: Player) -> None:
        if self.lead is None:
            player.enqueue(
                app.packets.notification(
                    "the leader has disconnected, please request another invite",
                ),
            )
            return
        group = groups.get_group(self.lead)
        if group is None:
            player.enqueue(
                app.packets.notification(
                    "the leader has disconnected, please request another invite",
                ),
            )
            return
        if player not in group.invites:
            player.enqueue(app.packets.notification("Your invite is invalid"))
            return
        group.add_player(player)


@register(ClientPackets.DISBAND_GROUP)
class disbandGroup(BasePacket):
    """Handle group disbandment requests.

    This packet handler processes the DISBAND_GROUP packet, which is used
    when a group leader wants to dissolve the group.
    """

    async def handle(self, player: Player) -> None:
        group = groups.get_group(player)
        if group is None or group.lead is not player:
            return
        group.disband()


@register(ClientPackets.INVITE_GROUP)
class inviteGroup(BasePacket):
    """Handle group invitation requests.

    This packet handler processes the INVITE_GROUP packet, which is used
    when a group leader wants to invite another player to the group.
    """

    def __init__(self, reader: BanchoPacketReader) -> None:
        self.target = players.get(id=reader.read_i32())

    async def handle(self, player: Player) -> None:
        if self.target is None:
            player.enqueue(app.packets.notification("the target is not online"))
            return
        group = groups.get_group(player)
        if group is None:
            player.enqueue(app.packets.notification("Your group is invalid"))
            return
        if group.lead is not player:
            player.enqueue(app.packets.notification("Your group is invalid"))
            return

        if self.target in group.invites:
            group.add_player(self.target)


@register(ClientPackets.GROUP_KICK)
class kickGroup(BasePacket):
    """Handle group member kick requests.

    This packet handler processes the GROUP_KICK packet, which is used
    when a group leader wants to remove a member from the group.
    """

    def __init__(self, reader: BanchoPacketReader) -> None:
        self.target = players.get(id=reader.read_i32())

    async def handle(self, player: Player) -> None:
        if self.target is None:
            player.enqueue(app.packets.notification("the target is not online"))
            return
        group = groups.get_group(player)
        if group is None or group.lead is not player:
            player.enqueue(app.packets.notification("Your group is invalid"))
            return

        if self.target in group.players:
            group.remove_user(self.target, True)


@register(ClientPackets.GROUP_LEAVE)
class leaveGroup(BasePacket):
    """Handle group departure requests.

    This packet handler processes the GROUP_LEAVE packet, which is used
    when a player wants to leave their current group.
    """

    async def handle(self, player: Player) -> None:
        group = groups.get_group(player)
        if group is None:
            return
        if group.lead is player:
            group.disband()
        else:
            group.remove_user(player)
