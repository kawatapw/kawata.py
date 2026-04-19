"""
Discord Integration Module - Webhook and Embed Management

This module provides Discord webhook functionality for the osu! server
application, enabling automated notifications and rich embed messages to
Discord channels. It implements Discord's webhook API for posting messages
with embedded content, images, and other media.

The module defines data classes for Discord embed components and a Webhook
class that handles the construction and posting of webhook payloads. It
includes retry logic for reliable message delivery and supports various
embed types including text, images, videos, and custom fields.

Key Features:
    - Discord webhook message posting with retry logic
    - Rich embed support with multiple component types
    - Image, video, and thumbnail embedding
    - Custom fields and footer support
    - Author and provider information
    - Color and timestamp customization
    - File attachment support
    - Automatic payload validation and formatting

Integration Points:
    - HTTP client in app/state/services.py
    - Logging system in app/logging.py
    - Settings configuration in app/settings.py
    - Application state in app/state/__init__.py

Discord Components:
    - Embed: Rich message container with multiple content types
    - Footer: Bottom section with text and optional icon
    - Image: Full-size image display
    - Thumbnail: Small preview image
    - Video: Video content embedding
    - Provider: Source information display
    - Author: Message author information
    - Field: Custom labeled content sections
    - Webhook: Message delivery mechanism

Usage Pattern:
    # Create a webhook for posting to Discord
    webhook = Webhook(url="https://discord.com/api/webhooks/...")

    # Create an embed with content
    embed = Embed(
        title="Server Update",
        description="New features have been added!",
        color=0x00ff00
    )

    # Add fields to the embed
    embed.add_field(name="Feature", value="New PP system", inline=True)
    embed.add_field(name="Status", value="Active", inline=True)

    # Add footer and image
    embed.set_footer(text="osu! server", icon_url="https://...")
    embed.set_image(url="https://...")

    # Add embed to webhook and post
    webhook.add_embed(embed)
    await webhook.post()

Related Files:
    - app/state/services.py: HTTP client for webhook requests
    - app/settings.py: Discord webhook URL configuration
    - app/logging.py: Logging utilities for webhook errors
"""

from __future__ import annotations

from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.state import services


class Footer:
    def __init__(self, text: str, **kwargs: Any) -> None:
        self.text = text
        self.icon_url = kwargs.get("icon_url")
        self.proxy_icon_url = kwargs.get("proxy_icon_url")


class Image:
    def __init__(self, **kwargs: Any) -> None:
        self.url = kwargs.get("url")
        self.proxy_url = kwargs.get("proxy_url")
        self.height = kwargs.get("height")
        self.width = kwargs.get("width")


class Thumbnail:
    def __init__(self, **kwargs: Any) -> None:
        self.url = kwargs.get("url")
        self.proxy_url = kwargs.get("proxy_url")
        self.height = kwargs.get("height")
        self.width = kwargs.get("width")


class Video:
    def __init__(self, **kwargs: Any) -> None:
        self.url = kwargs.get("url")
        self.height = kwargs.get("height")
        self.width = kwargs.get("width")


class Provider:
    def __init__(self, **kwargs: str) -> None:
        self.url = kwargs.get("url")
        self.name = kwargs.get("name")


class Author:
    def __init__(self, **kwargs: str) -> None:
        self.name = kwargs.get("name")
        self.url = kwargs.get("url")
        self.icon_url = kwargs.get("icon_url")
        self.proxy_icon_url = kwargs.get("proxy_icon_url")


class Field:
    def __init__(self, name: str, value: str, inline: bool = False) -> None:
        self.name = name
        self.value = value
        self.inline = inline


class Embed:
    def __init__(self, **kwargs: Any) -> None:
        self.title = kwargs.get("title")
        self.type = kwargs.get("type")
        self.description = kwargs.get("description")
        self.url = kwargs.get("url")
        self.timestamp = kwargs.get("timestamp")  # datetime
        self.color = kwargs.get("color", 0x000000)

        self.footer: Footer | None = kwargs.get("footer")
        self.image: Image | None = kwargs.get("image")
        self.thumbnail: Thumbnail | None = kwargs.get("thumbnail")
        self.video: Video | None = kwargs.get("video")
        self.provider: Provider | None = kwargs.get("provider")
        self.author: Author | None = kwargs.get("author")

        self.fields: list[Field] = kwargs.get("fields", [])

    def set_footer(self, **kwargs: Any) -> None:
        self.footer = Footer(**kwargs)

    def set_image(self, **kwargs: Any) -> None:
        self.image = Image(**kwargs)

    def set_thumbnail(self, **kwargs: Any) -> None:
        self.thumbnail = Thumbnail(**kwargs)

    def set_video(self, **kwargs: Any) -> None:
        self.video = Video(**kwargs)

    def set_provider(self, **kwargs: Any) -> None:
        self.provider = Provider(**kwargs)

    def set_author(self, **kwargs: Any) -> None:
        self.author = Author(**kwargs)

    def add_field(self, name: str, value: str, inline: bool = False) -> None:
        self.fields.append(Field(name, value, inline))


class Webhook:
    """A class to represent a single-use Discord webhook."""

    def __init__(self, url: str, **kwargs: Any) -> None:
        self.url = url
        self.content = kwargs.get("content")
        self.username = kwargs.get("username")
        self.avatar_url = kwargs.get("avatar_url")
        self.tts = kwargs.get("tts")
        self.file = kwargs.get("file")
        self.embeds = kwargs.get("embeds", [])

    def add_embed(self, embed: Embed) -> None:
        self.embeds.append(embed)

    @property
    def json(self) -> Any:
        if not any([self.content, self.file, self.embeds]):
            raise Exception(
                "Webhook must contain at least one of (content, file, embeds).",
            )

        if self.content and len(self.content) > 2000:
            raise Exception("Webhook content must be under 2000 characters.")

        payload: dict[str, Any] = {"embeds": []}

        for key in ("content", "username", "avatar_url", "tts", "file"):
            val = getattr(self, key)
            if val is not None:
                payload[key] = val

        for embed in self.embeds:
            embed_payload = {}

            # simple params
            for key in ("title", "type", "description", "url", "timestamp", "color"):
                val = getattr(embed, key)
                if val is not None:
                    embed_payload[key] = val

            # class params, must turn into dict
            for key in ("footer", "image", "thumbnail", "video", "provider", "author"):
                val = getattr(embed, key)
                if val is not None:
                    embed_payload[key] = val.__dict__

            if embed.fields:
                embed_payload["fields"] = [f.__dict__ for f in embed.fields]

            payload["embeds"].append(embed_payload)

        return payload

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def post(self) -> None:
        """Post the webhook in JSON format."""
        # TODO: if `self.file is not None`, then we should
        #       use multipart/form-data instead of json payload.
        headers = {"Content-Type": "application/json"}
        response = await services.http_client.post(
            self.url,
            json=self.json,
            headers=headers,
        )
        response.raise_for_status()
