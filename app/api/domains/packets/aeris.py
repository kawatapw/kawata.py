from typing import Mapping, TypedDict
from .common import *
from app.logging import Ansi, log
from app.constants.aeris_features import AerisFeatures
from app.objects.group import Group
from app.packets import BanchoPacketReader
from app.objects.player import Player
from app.state.sessions import *
import app.settings

AERIS_SERVER_FEATURES = AerisFeatures.Groups
if (app.settings.CHEAT_SERVER):
    AERIS_SERVER_FEATURES |= AerisFeatures.Cheats

@register(ClientPackets.IDENTIFY, restricted=True)
class AerisIdentify(BasePacket):
    def __init__(self, reader: BanchoPacketReader):
        self.features = reader.read_i32()
    async def handle(self, player: Player) -> None:
        server_features = 0 if player.restricted else AERIS_SERVER_FEATURES
        player.enqueue(app.packets.identify(server_features))
        # This identify an Aeris client from a PPY Client or any other client
        # used primarly to enable serverside features for this client
        log(f"user {player.name} ({player.id}) is using an Aeris client with the flags {self.features}", Ansi.BLUE)
        player.aeris_client = True
        player.aeris_client_features = self.features
        

@register(ClientPackets.CREATE_GROUP)
class CreateGroup(BasePacket):
    async def handle(self, player:Player):
        log(f"user {player.name} ({player.id}) making group", Ansi.BLUE)
        old_group = groups.get_group(player)
        if old_group is not None:
            old_group.remove_user(player)
        Group(player)

@register(ClientPackets.CREATE_GROUP_MATCH)
@register(ClientPackets.DISMOUNT_GROUP_MATCH)
class unavail(BasePacket):
    async def handle(self, player:Player):
        player.enqueue(app.packets.notification("this feature is not yet available"))

@register(ClientPackets.GROUP_USERS)
class GroupUsers(BasePacket):
    async def handle(self, player:Player):
        group = groups.get_group(player)
        if group is not None:
            player.enqueue(app.packets.group_users(player))

@register(ClientPackets.ACCEPT_GROUP)
class acceptGroup(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.lead = players.get(id=reader.read_i32())
    async def handle(self, player:Player):
        if self.lead is None:
            player.enqueue(app.packets.notification("the leader has disconnected, please request another invite"))
            return
        group = groups.get_group(self.lead)
        if not player in group.invites:
            player.enqueue(app.packets.notification("Your invite is invalid"))
            return
        group.add_player(player)


@register(ClientPackets.DISBAND_GROUP)
class disbandGroup(BasePacket):
    async def handle(self, player:Player):
        group = groups.get_group(player)
        if group is None or group.lead is not player:
            return
        group.disband()

@register(ClientPackets.INVITE_GROUP)
class inviteGroup(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.target = players.get(id=reader.read_i32())
    async def handle(self, player:Player):
        if self.target is None:
            player.enqueue(app.packets.notification("the target is not online"))
            return
        group = groups.get_group(player)
        if group is None or group.lead is not player:
            player.enqueue(app.packets.notification("Your group is invalid"))
            return
        
        if not self.target in group.invites:
            group.add_player(player)

@register(ClientPackets.GROUP_KICK)
class kickGroup(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.target = players.get(id=reader.read_i32())
    async def handle(self, player:Player):
        if self.target is None:
            player.enqueue(app.packets.notification("the target is not online"))
            return
        group = groups.get_group(player)
        if group is None or group.lead is not player:
            player.enqueue(app.packets.notification("Your group is invalid"))
            return
        
        if self.target in group.players:
            group.remove_user(player, True)

@register(ClientPackets.GROUP_LEAVE)
class leaveGroup(BasePacket):
    async def handle(self, player:Player):
        group = groups.get_group(player)
        if group is None:
            return
        if group.lead is player:
            group.disband()
        else:
            group.remove_user(player)