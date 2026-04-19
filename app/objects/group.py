"""
Group Module - Player Group Management System

This module defines the Group class, which represents a player group in the osu!
server application. Groups are temporary social constructs that allow players to
organize for multiplayer matches, spectating sessions, or other collaborative
activities. Each group has a leader, members, and an associated private channel
for communication.

The Group class manages the complete lifecycle of player groups including creation,
invitation, membership management, leadership delegation, and disbandment. It
integrates with the packet system to provide real-time updates to group members
and supports both standard osu! clients and enhanced group-capable clients.

Key Features:
    - Automatic group creation with unique token generation
    - Private channel creation for group communication
    - Invitation system with player notification
    - Membership management with join/leave functionality
    - Leadership delegation capabilities
    - Integration with multiplayer match system
    - Real-time packet updates for group members
    - Support for enhanced group-capable clients

Integration Points:
    - Player management in app/objects/player.py
    - Channel management in app/objects/channel.py
    - Packet handling in app/packets.py
    - Session management in app/state/sessions.py
    - Match system in app/objects/match.py

Group Structure:
    - lead: The player who created and leads the group
    - players: List of current group members
    - invites: List of players who have been invited
    - token: Unique identifier for the group
    - channel: Private channel for group communication
    - Match: Associated multiplayer match (if any)

Group Lifecycle:
    1. Creation: Leader creates group, gets unique token and channel
    2. Invitation: Leader invites other players to join
    3. Joining: Invited players accept and become members
    4. Communication: Members use private channel for coordination
    5. Match Creation: Group can create multiplayer matches
    6. Leadership: Leader can delegate leadership to another member
    7. Disbandment: Group is dissolved and channel removed

Packet Integration:
    - group_join(): Sent when player joins group
    - group_leave(): Sent when player leaves group
    - group_invite(): Sent when player is invited
    - group_users(): Sent to update group member list
    - notification(): Sent for group events

Usage Pattern:
    # Create a group
    group = Group(lead_player)

    # Invite a player
    group.invite(target_player)

    # Add player to group (after invitation)
    group.add_player(player)

    # Remove player from group
    group.remove_user(player)

    # Delegate leadership
    group.delegate(new_leader)

    # Disband group
    group.disband()

Related Files:
    - app/objects/player.py: Player class with group interactions
    - app/objects/channel.py: Channel class for group communication
    - app/packets.py: Packet creation for group updates
    - app/state/sessions.py: Session management with group tracking
    - app/objects/match.py: Match system integration
"""

import uuid

import app
from app.objects.channel import Channel
from app.objects.player import Player


class Group:
    def __init__(self, lead: Player):
        self.players: list[Player] = [lead]
        self.lead: Player = lead
        found = False
        token = ""
        while not found:
            token = str(uuid.uuid4())
            if app.state.sessions.groups.check_token(token):
                found = True
        self.token: str = token
        self.invites: list[Player] = []
        self.channel: Channel = Channel(
            f"#group_{self.token}",
            topic="Private group",
            instance=True,
            auto_join=False,
        )
        app.state.sessions.channels.append(self.channel)
        app.state.sessions.groups.append(self)
        lead.join_channel(self.channel)

        self.Match = None

        self.channel.send_bot("Your group has been created")
        lead.enqueue(app.packets.notification("group has been created"))
        if lead.has_group_capability:
            lead.enqueue(app.packets.group_join())
            lead.enqueue(app.packets.group_users(lead))

    def invite(self, player: Player) -> None:
        if player in self.players:
            return
        if player in self.invites:
            return
        self.invites.append(player)
        if player.has_group_capability:
            player.enqueue(app.packets.group_invite(self.lead))
        else:
            player.send_bot(
                f"You got a new group invite from {self.lead.name}.\ndo !accept {self.lead.safe_name} to accept it",
            )

    def make_match(self) -> None:
        self.lead.send_bot("Matches are not currently implemented.")

    def add_player(self, player: Player) -> None:
        if player in self.invites:
            self.invites.remove(player)
        self.players.append(player)
        if player.has_group_capability:
            player.enqueue(app.packets.group_join())
        for p in self.players:
            p.enqueue(
                app.packets.notification(
                    f"{'you' if p is player else player.name} joined the group",
                ),
            )
            if p.has_group_capability:
                p.enqueue(app.packets.group_users(p))
        player.join_channel(self.channel)
        self.channel.send_bot(f"{player.name} joined the group")

    def remove_user(self, player: Player, kick: bool = False) -> None:
        player.leave_channel(self.channel)
        self.players.remove(player)
        if player.has_group_capability:
            player.enqueue(app.packets.group_leave())

        if kick:
            self.channel.send_bot(f"{player.name} has been kicked out of the group")
        else:
            self.channel.send_bot(f"{player.name} left the group")

        if kick:
            player.enqueue(
                app.packets.notification(
                    "You have been kicked out of the group",
                ),
            )
        else:
            player.enqueue(app.packets.notification("You have left the group"))

        if not self.players:
            self.disband()
            return

        if player is self.lead:
            self.lead = self.players[0]
            self.channel.send_bot(f"Lead is now {self.lead.name}")

        for p in self.players:
            p.enqueue(
                app.packets.notification(f"{player.name} left the group"),
            )
            if p.has_group_capability:
                p.enqueue(app.packets.group_users(p))

    def delegate(self, player: Player) -> None:
        self.lead = player
        for p in self.players:
            if p.has_group_capability:
                p.enqueue(app.packets.group_users(p))
        self.channel.send_bot(f"Lead is now {player.name}")

    def disband(self) -> None:
        if self not in app.state.sessions.groups:
            return
        app.state.sessions.groups.remove(self)
        for p in self.players[:]:
            p.enqueue(app.packets.notification("group has been disbanded"))
            if p.has_group_capability:
                p.enqueue(app.packets.group_leave())
            p.leave_channel(self.channel)
        self.players.clear()
        self.invites.clear()
