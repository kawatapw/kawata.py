"""
Privileges Module - User Permission and Access Control Constants

This module defines privilege constants and utilities for managing user permissions
and access control throughout the osu! server application. It provides a comprehensive
hierarchical permission system that controls what actions users can perform, what
information they can access, and what administrative capabilities they possess.

The module contains three main privilege classes:
1. Privileges: Server-side user permissions for administrative and moderation functions
2. ClientPrivileges: Client-side permissions sent to the osu! client for UI display
3. ClanPrivileges: Clan-specific permissions for clan management

Key Features:
    - Hierarchical permission system with inheritance
    - Bitwise flag operations for efficient permission checking
    - Group-based permission management (STAFF, MODERATOR, etc.)
    - Conversion utilities between integer and privilege representations
    - Support for both individual and combined privilege checking

Integration Points:
    - User authentication in app/api/domains/cho.py
    - Administrative functions in app/api/v2/players.py
    - Moderation tools in app/api/domains/osu.py
    - Clan management in app/repositories/clans.py
    - Database storage in app/repositories/users.py

Permission Hierarchy:
    - BANNED (0): No permissions, user is restricted
    - UNRESTRICTED (1): Basic user permissions
    - VERIFIED (2): Has logged in to the server in-game
    - SUPPORTER (4): Financial supporter of the server
    - AccessPanel (8): Access to administrative panel
    - ManageUsers (16): Can manage user accounts
    - BanUsers (32): Can ban users
    - SilenceUsers (64): Can silence users
    - WipeUsers (128): Can wipe user data
    - ManageBeatmaps (256): Can manage beatmap rankings
    - ManageBadges (8192): Can manage user badges
    - ViewPanelLog (16384): Can view administrative logs
    - ManagePrivs (32768): Can manage user privileges
    - SendAlerts (65536): Can send in-game alerts
    - ChatMod (131072): Chat moderation permissions
    - KickUsers (262144): Can kick users from server
    - TOURNEY_MANAGER (1048576): Can manage tournament matches
    - ManageClans (134217728): Can manage clan operations
    - ViewSensitiveInfo (268435456): Can view sensitive user data
    - IsBot (1073741824): Bot account flag
    - WHITELISTED (2147483648): Trusted user with anticheat bypass
    - PREMIUM (4294967296): Premium donor status
    - ALUMNI (8589934592): Notable user status
    - DEVELOPER (17179869184): Full server management access

Permission Groups:
    - NOMINATOR: Beatmap nomination permissions
    - SUPPORT: Basic moderation permissions
    - MODERATOR: Extended moderation permissions
    - ADMINISTRATOR: Full administrative permissions
    - DONATOR: Supporter and premium combined
    - STAFF: All staff permissions combined

Usage Pattern:
    - Privileges are stored as bitwise integers in user data
    - Permission checking uses bitwise AND operations
    - Group permissions are combinations of individual privileges
    - The GetPriv() function converts between integer and privilege representations

Example Usage:
    # Check if user has specific permission
    if user.privileges & Privileges.BanUsers:
        ban_user(target_user)

    # Check if user has all permissions in a group
    if user.privileges & Privileges.MODERATOR == Privileges.MODERATOR:
        grant_moderator_access()

    # Convert integer to privilege list
    priv_list = GetPriv(user.privileges)

    # Convert privilege list to integer
    priv_int = GetPriv([Privileges.BanUsers, Privileges.SilenceUsers])

Related Files:
    - app/objects/player.py: Player class storing privilege data
    - app/api/domains/cho.py: Client connection with privilege validation
    - app/api/v2/players.py: Player management with privilege checks
    - app/repositories/users.py: Database operations for privilege storage
"""

from __future__ import annotations

from enum import IntEnum
from enum import IntFlag
from enum import unique

from app.utils import escape_enum
from app.utils import pymysql_encode


@unique
@pymysql_encode(escape_enum)
class Privileges(IntFlag):
    """Server side user privileges."""

    BANNED = 0  # 0 Perms, Banned or Restricted, whatever you want to call it.
    UNRESTRICTED = 1  # user is not restricted.
    VERIFIED = 2 << 0  # has logged in to the server in-game. (2)
    SUPPORTER = 2 << 1  # user is a supporter. (4)
    AccessPanel = 2 << 2  # probably wont be used much. (8)
    ManageUsers = (
        2 << 3
    )  # can manage users? probably going to be used for changing passwords/email/etc (16)
    BanUsers = 2 << 4  # can ban users (32)
    SilenceUsers = 2 << 5  # can silence users (64)
    WipeUsers = 2 << 6  # can wipe users (128)
    ManageBeatmaps = 2 << 7  # able to manage maps ranked status. (256)
    ManageBadges = 2 << 13  # can manage badges (8192)
    ViewPanelLog = 2 << 14  # can view the panel log (16384)
    ManagePrivs = 2 << 15  # can manage privs of users (32768)
    SendAlerts = (
        2 << 16
    )  # can send in-game alerts? probably not going to be used much (65536)
    ChatMod = 2 << 17  # chat mod, no way (131072)
    KickUsers = 2 << 18  # can kick users (262144)
    TOURNEY_MANAGER = 2 << 20  # able to manage match state without host. (1048576)
    ManageClans = 2 << 27  # can manage clans. (134217728)
    ViewSensitiveInfo = (
        2 << 28
    )  # can view ips, hwids, disk ids of users. super awesome with the new system. (268435456)
    IsBot = 2 << 30  # BOT_USER (1073741824)
    WHITELISTED = (
        2 << 31
    )  # has bypass to low-ceiling anticheat measures (trusted). (2147483648)
    PREMIUM = 2 << 32  # 'premium' donor (4294967296)
    ALUMNI = 2 << 33  # notable users, receives some extra benefits. (8589934592)
    DEVELOPER = 2 << 34  # able to manage full server app.state. (17179869184)

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
    SUPPORT = (
        BanUsers
        | SilenceUsers
        | WipeUsers
        | KickUsers
        | ChatMod
        | ViewPanelLog
        | SendAlerts
        | ManageClans
        | AccessPanel
    )
    MODERATOR = (
        SUPPORT | ManageUsers | ManageBadges | ViewSensitiveInfo
    )  # define this as a moderator
    ADMINISTRATOR = (
        MODERATOR | ManagePrivs
    )  # has moderator privileges, can view sensitive info and manage users

    DONATOR = SUPPORTER | PREMIUM
    STAFF = NOMINATOR | SUPPORT | MODERATOR | ADMINISTRATOR | DEVELOPER


def GetPriv(priv: int | list[Privileges]) -> int | list[Privileges]:
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
        if priv < 0:
            raise ValueError("Privilege value cannot be negative")
        privs: int | list[Privileges] = [
            p for p in Privileges if p.value != 0 and priv & p.value == p.value
        ]

    elif isinstance(priv, list):
        if not all(isinstance(p, Privileges) for p in priv):
            raise TypeError(
                "Privilege must be an int or a list of instances of Privileges",
            )
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
