from __future__ import annotations

from enum import IntEnum
from enum import IntFlag
from enum import unique

from app.utils import escape_enum
from app.utils import pymysql_encode

from typing import Union
from typing import List

__all__ = ("Privileges", "ClientPrivileges", "ClanPrivileges")


@unique
@pymysql_encode(escape_enum)
class Privileges(IntFlag):
    """Server side user privileges."""
    BANNED              = 0        # 0 Perms, Banned or Restricted, whatever you want to call it.
    UNRESTRICTED        = 1        # user is not restricted.
    VERIFIED            = 2 << 0   # has logged in to the server in-game.
    SUPPORTER           = 2 << 1   # user is a supporter.
    AccessPanel         = 2 << 2   # probably wont be used much.    
    ManageUsers         = 2 << 3   # can manage users? probably going to be used for changing passwords/email/etc
    BanUsers            = 2 << 4   # can ban users
    SilenceUsers        = 2 << 5   # can silence users
    WipeUsers           = 2 << 6   # can wipe users
    ManageBeatmaps      = 2 << 7   # able to manage maps ranked status.
    ManageBadges        = 2 << 13  # can manage badges
    ViewPanelLog        = 2 << 14  # can view the panel log
    ManagePrivs         = 2 << 15  # can manage privs of users
    SendAlerts          = 2 << 16  # can send in-game alerts? probably not going to be used much
    ChatMod             = 2 << 17  # chat mod, no way
    KickUsers           = 2 << 18  # can kick users
    TOURNEY_MANAGER     = 2 << 20  # able to manage match state without host.
    ManageClans         = 2 << 27  # can manage clans.
    ViewSensitiveInfo   = 2 << 28  # can view ips, hwids, disk ids of users. super awesome with the new system.
    IsBot               = 2 << 30  # BOT_USER
    WHITELISTED         = 2 << 31  # has bypass to low-ceiling anticheat measures (trusted).
    PREMIUM             = 2 << 32  # 'premium' donor
    ALUMNI              = 2 << 33  # notable users, receives some extra benefits.
    DEVELOPER           = 2 << 34  # able to manage full server app.state.


    # groups inherently say they "are part of" the things they contain.
    # e.g. if you have the AccessPanel privilege, you are also a Moderator, Admin, and Nominator..
    # like... it thinks you are all of those things. a pain in my ass.
    # so, when operating with privileges. please use the following syntax, or just use GetPriv, since its already coded.
    # Format:
    # if user_priv & Privileges.Mod == Privileges.Mod
    # this is to check if a user has ALL privileges in a group; like mod.
    # to check if a privilege is IN a group, like donator, or staff,  you do
    # if user_priv & Privileges.Donator. thats it.
    
    NOMINATOR = ManageBeatmaps | AccessPanel
    MODERATOR = BanUsers | SilenceUsers | WipeUsers | KickUsers| ManagePrivs | ChatMod | ManageUsers  # define this as a moderator
    ADMINISTRATOR = MODERATOR | ViewSensitiveInfo # has moderator privileges, can view sensitive info and manage users
    

    DONATOR = SUPPORTER | PREMIUM
    STAFF = MODERATOR | ADMINISTRATOR | DEVELOPER

def GetPriv(priv: Union[int, List[Privileges]]) -> Union[int, List[Privileges]]:
    """
    Get the privileges based on the given input.

    Args:
        priv (Union[int, List[Privileges]]): The input representing the privileges. It can be either an integer or a list of Privileges instances.

    Returns:
        Union[int, List[Privileges]]: The privileges based on the input. 
        If the input is an integer, it returns a list of Privileges instances that match the input. 
        If the input is a list of Privileges instances, it returns an integer representing the combined privileges.

    Raises:
        TypeError: If the input is not an integer or a list of Privileges instances.
        ValueError: If no privileges are found.
    """
    if isinstance(priv, int):
        privs = [p for p in Privileges if p.value != 0 and priv & p.value == p.value]

    elif isinstance(priv, list) and all(isinstance(p, Privileges) for p in priv):
        privs = 0
        for p in priv:
            privs |= p.value
    else:
        raise TypeError("Privilege must be an int or a list of instances of Privileges")

    if not privs:
        raise ValueError("No Privileges")

    return privs


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
