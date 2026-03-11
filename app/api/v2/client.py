""" bancho.py's v2 apis for interacting with client specific data """
from __future__ import annotations
import textwrap
from typing import Any

from fastapi import APIRouter
from fastapi import status
from fastapi.param_functions import Query

from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import success
from app.api.v2.common.responses import Success
from app.state.services import database
from app.logging import log

router = APIRouter()

READ_PARAMS = textwrap.dedent(
    """\
        type, category, poster, content, time, version
    """,
)

@router.get("/changelog")
async def get_changelog(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    change_type: int | None = Query(None, ge=0, le=2),
    category: str | None = None,
    unix_from: int = 0,
) -> Success[list[dict[str, Any]]] | Failure:
    try:
        params: dict[str, Any] = {}
        query = f"""\
            SELECT {READ_PARAMS}
              FROM changelog
            """
        accessor = "WHERE" # used to add ANDs to the query

        if (change_type is not None):
            query += accessor + " type = :type "
            accessor = "AND"
            params["type"] = change_type

        if (category is not None):
            query += accessor + " category = :category "
            accessor = "AND"
            params["category"] = category

        query += accessor + " UNIX_TIMESTAMP(time) >= :unix_from "

        query += """
                LIMIT :limit
                OFFSET :offset
            """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size
        params["unix_from"] = unix_from

        data = await database.fetch_all(query, params)
        if data is None:
            return responses.failure(
                message="An error occurred while fetching changelog.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        meta = {
            "total": len(data),
            "page": page,
            "page_size": page_size,
            "type": change_type,
            "category": category,
            "unix_from": unix_from
        }
        res = []
        for row in data:
            res.append({
                "type": row["type"],
                "category": row["category"], 
                "poster": row["poster"],
                "content": row["content"],
                "time": row["time"].strftime("%Y-%m-%d %H:%M:%S"),
                "version": row["version"]
            })
        return responses.success(content=res, meta=meta)
    except Exception as e:
        log(f"Error in get_changelog: {e}")
        return responses.failure(
            message="An error occurred while fetching changelog.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )