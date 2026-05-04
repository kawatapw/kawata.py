from __future__ import annotations


def cover_urls(set_id: int) -> dict[str, str]:
    base = f"https://assets.ppy.sh/beatmaps/{set_id}/covers"
    return {
        "cover_url": f"{base}/cover@2x.jpg",
        "cover_url_1x": f"{base}/cover.jpg",
        "thumbnail_url": f"{base}/card@2x.jpg",
        "list_url": f"{base}/list@2x.jpg",
        "preview_url": f"https://b.ppy.sh/preview/{set_id}.mp3",
    }
