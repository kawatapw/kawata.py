"""
Nominator Commands

Commands for nominator role.
"""

from __future__ import annotations

import time

from app import settings
from app.commands.base import nominator_command
from app.commands.context import Context
from app.logging import Ansi
from app.logging import log
from app.objects.beatmap import Beatmap
from app.objects.beatmap import RankedStatus
from app.repositories import map_requests as map_requests_repo
from app.repositories import maps as maps_repo


@nominator_command(
    name="request",
    triggers=["request", "req"],
    description="Request a beatmap for nomination.",
)
async def request(ctx: Context) -> str:
    """Request a beatmap for nomination."""
    if ctx.args:
        return "Invalid syntax: !request"

    if ctx.player.last_np is None or time.time() >= ctx.player.last_np["timeout"]:
        return "Please /np a map first!"

    bmap = ctx.player.last_np["bmap"]

    if bmap.status != RankedStatus.Pending and settings.REQUEST_PENDING_ONLY:
        return "Only pending maps may be requested for status change."

    map_requests = await map_requests_repo.fetch_all(
        map_id=bmap.id,
        player_id=ctx.player.id,
        active=True,
    )
    if map_requests:
        return "You already have an active nomination request for that map."

    await map_requests_repo.create(map_id=bmap.id, player_id=ctx.player.id, active=True)

    return "Request submitted."


@nominator_command(
    name="requests",
    triggers=["requests", "reqs"],
    description="Check the nomination request queue.",
    hidden=True,
)
async def requests(ctx: Context) -> str:
    """Check the nomination request queue."""
    if ctx.args:
        return "Invalid syntax: !requests"

    rows = await map_requests_repo.fetch_all(active=True)

    if not rows:
        return "The queue is clean! (0 map request(s))"

    # group rows into {map_id: [map_request, ...]}
    grouped: dict[int, list[map_requests_repo.MapRequest]] = {}
    for row in rows:
        if row["map_id"] not in grouped:
            grouped[row["map_id"]] = []
        grouped[row["map_id"]].append(row)

    if not grouped:
        return "The queue is clean! (0 map request(s))"

    request_lines = [f"Total requested beatmaps: {len(grouped)}"]
    for map_id, reviews in grouped.items():
        if len(reviews) == 0:
            raise ValueError("Reviews list is empty")

        bmap = await Beatmap.from_bid(map_id)
        if not bmap:
            log(f"Failed to find requested map ({map_id})?", Ansi.LYELLOW)
            continue

        first_review = min(reviews, key=lambda r: r["datetime"])

        request_lines.append(
            f"{len(reviews)}x request(s) starting {first_review['datetime']:%Y-%m-%d}: {bmap.embed}",
        )

    return "\n".join(request_lines)


_status_str_to_int_map = {"unrank": 0, "rank": 2, "love": 5}


def status_to_id(s: str) -> int:
    return _status_str_to_int_map[s]


@nominator_command(
    name="_map",
    description="Changes the ranked status of the most recently /np'ed map.",
)
async def _map(ctx: Context) -> str:
    """Changes the ranked status of the most recently /np'ed map."""
    if (
        len(ctx.args) != 2
        or ctx.args[0] not in ("rank", "unrank", "love")
        or ctx.args[1] not in ("set", "map")
    ):
        return "Invalid syntax: !map <rank/unrank/love> <map/set>"

    if ctx.player.last_np is None or time.time() >= ctx.player.last_np["timeout"]:
        log(
            f"Player Last NP: {ctx.player.last_np}\nFull Context: {ctx}",
            Ansi.LBLUE,
            extra={
                "filter": {
                    "debugLevel": 2,
                },
            },
            level=14,
            logger="console.debug",
        )
        return "Please /np a map first!"

    bmap = ctx.player.last_np["bmap"]
    new_status = RankedStatus(status_to_id(ctx.args[0]))

    if ctx.args[1] == "map":
        if bmap.status == new_status:
            return f"{bmap.embed} is already {new_status!s}!"
    elif all(map.status == new_status for map in bmap.set.maps):
        return f"All maps from the set are already {new_status!s}!"

    # update sql & cache based on scope
    # XXX: not sure if getting md5s from sql
    # for updating cache would be faster?
    # surely this will not scale as well...

    async with ctx.state.services.database.transaction():
        if ctx.args[1] == "set":
            # update all maps in the set
            for _bmap in bmap.set.maps:
                await maps_repo.partial_update(_bmap.id, status=new_status, frozen=True)

            # make sure cache and db are synced about the newest change
            for _bmap in ctx.cache.beatmapset[bmap.set_id].maps:
                _bmap.status = new_status
                _bmap.frozen = True

            # select all map ids for clearing map requests.
            modified_beatmap_ids = [
                row["id"]
                for row in await maps_repo.fetch_many(
                    set_id=bmap.set_id,
                )
            ]

        else:
            # update only map
            await maps_repo.partial_update(bmap.id, status=new_status, frozen=True)

            # make sure cache and db are synced about the newest change
            if bmap.md5 in ctx.cache.beatmap:
                ctx.cache.beatmap[bmap.md5].status = new_status
                ctx.cache.beatmap[bmap.md5].frozen = True

            modified_beatmap_ids = [bmap.id]

        # deactivate rank requests for all ids
        await map_requests_repo.mark_batch_as_inactive(map_ids=modified_beatmap_ids)

    return f"{bmap.embed} updated to {new_status!s}."
