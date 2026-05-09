"""
Map Domain Module - Beatmap Static Asset Proxy

This module provides a simple proxy endpoint for beatmap static assets in the
osu! server application. It forwards any unmatched requests to the official
osu! beatmap CDN (b.ppy.sh) to serve static content like thumbnails, previews,
and other beatmap-related assets.

The module acts as a catch-all proxy that redirects requests to the official
osu! beatmap content delivery network. This allows the server to serve beatmap
assets without hosting them locally, reducing storage requirements and
leveraging osu!'s existing CDN infrastructure.

Key Features:
    - Proxy for beatmap static assets (thumbnails, previews, etc.)
    - Redirect to official osu! beatmap CDN
    - Support for any file path pattern
    - HTTP 301 permanent redirect for caching efficiency
    - Minimal overhead with simple redirect logic

Integration Points:
    - Beatmap management in app/objects/beatmap.py
    - API routing in app/api/init_api.py
    - Static asset serving for client requests
    - CDN integration for beatmap content

Supported Assets:
    - Beatmap thumbnails and previews
    - Audio previews and samples
    - Background images and storyboards
    - Other static beatmap-related files

Usage Pattern:
    # Request beatmap thumbnail
    GET /b/12345/thumbnail.jpg -> Redirects to https://b.ppy.sh/b/12345/thumbnail.jpg

    # Request beatmap preview
    GET /b/12345/preview.mp3 -> Redirects to https://b.ppy.sh/b/12345/preview.mp3

    # Request any beatmap asset
    GET /b/{beatmap_id}/{asset_path} -> Redirects to https://b.ppy.sh/b/{beatmap_id}/{asset_path}

Related Files:
    - app/objects/beatmap.py: Beatmap data model
    - app/api/init_api.py: API router initialization
    - app/settings.py: Server configuration settings
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import status
from fastapi.requests import Request
from fastapi.responses import RedirectResponse

# import app.settings

router = APIRouter(tags=["Beatmaps"])


# forward any unmatched request to osu!
# eventually if we do bmap submission, we'll need this.
@router.get("/{file_path:path}")
async def everything(request: Request, file_path: str) -> RedirectResponse:
    """Proxy any beatmap asset requests to the official osu! CDN.

    This endpoint acts as a catch-all proxy that redirects requests for
    beatmap static assets (thumbnails, previews, etc.) to the official
    osu! beatmap content delivery network at b.ppy.sh.

    Args:
        request: The incoming HTTP request containing the file path

    Returns:
        RedirectResponse: HTTP 301 redirect to the official osu! CDN

    Example:
        GET /b/12345/thumbnail.jpg -> Redirects to https://b.ppy.sh/b/12345/thumbnail.jpg
    """
    return RedirectResponse(
        url=f"https://b.ppy.sh{request['path']}",
        status_code=status.HTTP_301_MOVED_PERMANENTLY,
    )
