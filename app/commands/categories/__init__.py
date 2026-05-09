"""
Command Categories Package

Contains all command category implementations.
"""

from __future__ import annotations

from .administrator import alert
from .administrator import alertuser
from .administrator import restrict
from .administrator import shutdown
from .administrator import switchserv
from .administrator import unrestrict
from .administrator import user
from .clan import clan_create
from .clan import clan_disband
from .clan import clan_help
from .clan import clan_info
from .clan import clan_leave
from .clan import clan_list
from .developer import addpriv
from .developer import debug
from .developer import debug_focus
from .developer import givedonator
from .developer import recalc
from .developer import reload
from .developer import rmpriv
from .developer import server
from .developer import stealth
from .developer import wipemap

# py command is only available when DEVELOPER_MODE is enabled
from app import settings
if settings.DEVELOPER_MODE:
    from .developer import py
from .mappool import pool_add
from .mappool import pool_create
from .mappool import pool_delete
from .mappool import pool_help
from .mappool import pool_info
from .mappool import pool_list
from .mappool import pool_remove
from .moderator import addnote
from .moderator import notes
from .moderator import silence
from .moderator import unsilence
from .multiplayer import mp_abort
from .multiplayer import mp_addref
from .multiplayer import mp_condition
from .multiplayer import mp_endscrim
from .multiplayer import mp_force
from .multiplayer import mp_freemods
from .multiplayer import mp_help
from .multiplayer import mp_host
from .multiplayer import mp_invite
from .multiplayer import mp_listref
from .multiplayer import mp_loadpool
from .multiplayer import mp_lock
from .multiplayer import mp_map
from .multiplayer import mp_mods
from .multiplayer import mp_randpw
from .multiplayer import mp_rematch
from .multiplayer import mp_rmref
from .multiplayer import mp_scrim
from .multiplayer import mp_start
from .multiplayer import mp_teams
from .multiplayer import mp_unloadpool
from .multiplayer import mp_unlock
from .nominator import _map
from .nominator import request
from .nominator import requests
from .season import recalc_season_stats
from .season import season_create
from .season import season_end
from .season import season_list
from .season import season_schedule
from .season import season_start
from .season import seasons
from .season import seasons_all
from .user import _with
from .user import apikey
from .user import block
from .user import changename
from .user import help_cmd
from .user import maplink
from .user import recent
from .user import reconnect
from .user import roll
from .user import top
from .user import unblock

__all__ = [
    "_map",
    "_with",
    "addnote",
    "addpriv",
    "alert",
    "alertuser",
    "apikey",
    "block",
    "changename",
    "clan_create",
    "clan_disband",
    "clan_help",
    "clan_info",
    "clan_leave",
    "clan_list",
    "debug",
    "debug_focus",
    "givedonator",
    "help_cmd",
    "maplink",
    "mp_abort",
    "mp_addref",
    "mp_condition",
    "mp_endscrim",
    "mp_force",
    "mp_freemods",
    "mp_help",
    "mp_host",
    "mp_invite",
    "mp_listref",
    "mp_loadpool",
    "mp_lock",
    "mp_map",
    "mp_mods",
    "mp_randpw",
    "mp_rematch",
    "mp_rmref",
    "mp_scrim",
    "mp_start",
    "mp_teams",
    "mp_unloadpool",
    "mp_unlock",
    "notes",
    "pool_add",
    "pool_create",
    "pool_delete",
    "pool_help",
    "pool_info",
    "pool_list",
    "pool_remove",
    "recalc",
    "recalc_season_stats",
    "recent",
    "reconnect",
    "reload",
    "request",
    "requests",
    "restrict",
    "rmpriv",
    "roll",
    "season_create",
    "season_end",
    "season_list",
    "season_schedule",
    "season_start",
    "seasons",
    "seasons_all",
    "server",
    "shutdown",
    "silence",
    "stealth",
    "switchserv",
    "top",
    "unblock",
    "unrestrict",
    "unsilence",
    "user",
    "wipemap",
]

# Add py command to __all__ only if DEVELOPER_MODE is enabled
if settings.DEVELOPER_MODE:
    __all__.append("py")
