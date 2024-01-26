import uuid
from app.constants.aeris_features import AerisFeatures
from app.objects.channel import Channel
from app.objects.match import Match
from app.objects.player import Player
import app


class Group:
    def __init__(self, lead:Player):
        self.players: [Player] = [lead]
        self.lead = lead
        found = False
        token = ''
        while not found:
            token = str(uuid.uuid4())
            if app.state.sessions.groups.check_token(token):
                found = True
        self.token: str = token
        self.invites: [Player] = []
        self.channel : Channel = Channel(f'#group_{self.token}', 
                                         topic="Private group",
                                         instance=True,
                                         auto_join=False)
        app.state.sessions.channels.append(self.channel)
        app.state.sessions.groups.append(self)
        lead.join_channel(self.channel)

        self.Match = None

        self.channel.send_bot(f"Your group has been created")
        lead.enqueue(app.packets.notification("group has been created"))
        if (lead.has_group_capability):
            lead.enqueue(app.packets.group_join())
            lead.enqueue(app.packets.group_users(lead))
    
    def invite(self, player:Player):
        self.invite.append(player)
        if (player.has_group_capability):
            player.enqueue(app.packets.group_invite(self.lead))
        else:
            player.send_bot(f"You got a new group invite from {player.name}.\ndo !accept {player.safe_name} to accept it")

    def make_match(self):
        self.lead.send_bot("Matches are not currently implemented.")

    def add_player(self, player:Player):
        self.invites.remove(player)
        self.players.append(player)
        if (player.has_group_capability):
            player.enqueue(app.packets.group_join())
        for p in self.players:
            player.enqueue(app.packets.notification(f"{'you' if p is player else player.name} joined the group"))
            if (player.has_group_capability):
                player.enqueue(app.packets.group_users(p))
        player.join_channel(self.channel)
        self.channel.send_bot(f"{player.name} joined the group")

    def remove_user(self, player:Player, kick:bool=False):
        player.leave_channel(self.channel)
        self.players.remove(player)
        if player.has_group_capability:
            player.enqueue(app.packets.group_leave())

        if kick:
            self.channel.send_bot(f"{player.name} has been kicked out of the group")
        else:
            self.channel.send_bot(f"{player.name} left the group")

        for p in self.players:
            if (p == player):
                if kick:
                    player.enqueue(app.packets.notification("You have been kicked out of the group"))
                else:
                    player.enqueue(app.packets.notification("You have left the group"))
            else:
                player.enqueue(app.packets.notification(f"{player.name} left the group"))
            if (player.has_group_capability):
                player.enqueue(app.packets.group_users(p))
    
    def delegate(self, player:Player):
        self.lead = player
        for p in self.players:
            if p.has_group_capability:
                p.enqueue(app.packets.group_users(p))
        self.channel.send_bot(f'Lead is now {player.name}')
    
    def disband(self):
        app.state.sessions.groups.remove(self)
        for p in self.players:
            p.enqueue(app.packets.notification("group has been disbanded"))
            if (p.has_group_capability):
                p.enqueue(app.packets.group_leave())