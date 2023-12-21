from __future__ import annotations

from enum import IntEnum
from enum import IntFlag
from enum import unique

from app.utils import escape_enum
from app.utils import pymysql_encode

__all__ = ("Privileges", "ClientPrivileges", "ClanPrivileges")


@unique
@pymysql_encode(escape_enum)
class Privileges(IntFlag):
    """Server side user privileges."""
    BANNED              = 0        # not previously defined.
    UNRESTRICTED        = 1        # user is not restricted.
    VERIFIED            = 2 << 0   # has logged in to the server in-game.
    SUPPORTER           = 2 << 1   # user is a supporter.
    AccessPanel         = 2 << 2   # probably wont be used much.    
    ManageUsers         = 2 << 3   # can manage users? probably going to be used for changing passwords/email/etc
    BanUsers            = 2 << 4   # can ban users
    SilenceUsers        = 2 << 5   # can silence users
    WipeUsers           = 2 << 6   # can wipe users
    ManageBeatmaps      = 2 << 7   # able to manage maps ranked status.
    #ManageServers      = 2 << 8  
    #ManageSettings     = 2 << 9  
    #ManageBetaKeys     = 2 << 10  
    #ManageReports      = 2 << 11  
    #ManageDocs         = 2 << 12  
    ManageBadges        = 2 << 13  # can manage badges
    ViewPanelLog        = 2 << 14  # can view the panel log
    ManagePrivs         = 2 << 15  # can manage privs of users
    SendAlerts          = 2 << 16  # can send in-game alerts? probably not going to be used much
    ChatMod             = 2 << 17  # chat mod, no way
    KickUsers           = 2 << 18  # can kick users
    #PendingVerify      = 2 << 19  # completely deprecated, unused. dont use this.
    TOURNEY_MANAGER     = 2 << 20  # able to manage match state without host.
    #Caker              = 2 << 21  # what is this??
    ManageClans         = 2 << 27  # can manage clans.
    ViewSensitiveInfo   = 2 << 28  # can view ips, hwids, disk ids of users. super awesome with the new system.
    IsBot               = 2 << 30  # BOT_USER
    WHITELISTED         = 2 << 31  # has bypass to low-ceiling anticheat measures (trusted).
    PREMIUM             = 2 << 32  # 'premium' donor
    ALUMNI              = 2 << 33  # notable users, receives some extra benefits.
    DEVELOPER           = 2 << 34  # able to manage full server app.state.




    NOMINATOR = ManageBeatmaps | AccessPanel
    MODERATOR = BanUsers | SilenceUsers | WipeUsers | KickUsers| ManagePrivs | ChatMod # define this as a moderator
    ADMINISTRATOR = MODERATOR | ViewSensitiveInfo | ManageUsers  # has moderator privileges, can view sensitive info and manage users
    

    DONATOR = SUPPORTER | PREMIUM
    STAFF = MODERATOR | ADMINISTRATOR | DEVELOPER


@unique
@pymysql_encode(escape_enum)
class ClientPrivileges(IntFlag):
    """Client side user privileges."""

    PLAYER = 1 << 0
    MODERATOR = 1 << 1
    SUPPORTER = 1 << 2
    OWNER = 1 << 3
    DEVELOPER = 1 << 4
    TOURNAMENT = 1 << 5  # NOTE: not used in communications with osu! client


@unique
@pymysql_encode(escape_enum)
class ClanPrivileges(IntEnum):
    """A class to represent a clan members privs."""

    Member = 1
    Officer = 2
    Owner = 3
