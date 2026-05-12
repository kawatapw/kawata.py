# Phase 10 — Account Linking

## Scope

Implement bidirectional account linking between osu! and Discord accounts with verification codes.

## 1. Account Linking Service

### 1.1 `app/discord/services/account_linking_service.py`

```python
"""Discord-osu! account linking service."""

from __future__ import annotations

import secrets
import string
import time
from typing import Any

from app.discord.repositories import discord_repositories
from app.logging import Ansi
from app.logging import log


# In-memory store for pending link codes (could be moved to Redis for persistence)
_pending_codes: dict[str, dict[str, Any]] = {}


class AccountLinkingService:
    """Service for linking osu! and Discord accounts."""

    CODE_LENGTH = 8
    CODE_EXPIRY = 600  # 10 minutes

    def generate_link_code(
        self,
        osu_user_id: int | None = None,
        discord_user_id: int | None = None,
    ) -> str:
        """
        Generate a unique link code.

        Args:
            osu_user_id: osu! user ID (if linking from Discord).
            discord_user_id: Discord user ID (if linking from osu!).

        Returns:
            Unique link code.
        """
        # Generate random code
        code = "".join(
            secrets.choice(string.ascii_uppercase + string.digits)
            for _ in range(self.CODE_LENGTH)
        )

        # Store pending link
        _pending_codes[code] = {
            "osu_user_id": osu_user_id,
            "discord_user_id": discord_user_id,
            "created_at": time.time(),
        }

        # Clean up expired codes
        self._cleanup_expired_codes()

        return code

    async def complete_link_from_osu(
        self,
        code: str,
        osu_user_id: int,
    ) -> tuple[bool, str]:
        """
        Complete account linking from osu! side.

        Args:
            code: Link code generated from Discord.
            osu_user_id: osu! user ID.

        Returns:
            Tuple of (success, message).
        """
        pending = _pending_codes.get(code)
        if not pending:
            return False, "Invalid or expired code."

        if pending.get("osu_user_id") is not None:
            return False, "This code is not for linking from osu!."

        discord_user_id = pending.get("discord_user_id")
        if not discord_user_id:
            return False, "Invalid code state."

        # Check if already linked
        existing = await discord_repositories.user.get_by_discord(discord_user_id)
        if existing:
            return False, "This Discord account is already linked."

        # Create link
        is_primary = not await discord_repositories.user.get_by_osu(osu_user_id)
        await discord_repositories.user.create(
            osu_user_id=osu_user_id,
            discord_user_id=discord_user_id,
            is_primary=is_primary,
        )

        # Remove pending code
        del _pending_codes[code]

        log(f"Linked osu! user {osu_user_id} to Discord user {discord_user_id}", Ansi.LGREEN)
        return True, "Successfully linked your Discord account!"

    async def complete_link_from_discord(
        self,
        code: str,
        discord_user_id: int,
    ) -> tuple[bool, str]:
        """
        Complete account linking from Discord side.

        Args:
            code: Link code generated from osu!.
            discord_user_id: Discord user ID.

        Returns:
            Tuple of (success, message).
        """
        pending = _pending_codes.get(code)
        if not pending:
            return False, "Invalid or expired code."

        if pending.get("discord_user_id") is not None:
            return False, "This code is not for linking from Discord."

        osu_user_id = pending.get("osu_user_id")
        if not osu_user_id:
            return False, "Invalid code state."

        # Check if Discord already linked
        existing = await discord_repositories.user.get_by_discord(discord_user_id)
        if existing:
            return False, "This Discord account is already linked to another osu! account."

        # Create link
        is_primary = not await discord_repositories.user.get_by_osu(osu_user_id)
        await discord_repositories.user.create(
            osu_user_id=osu_user_id,
            discord_user_id=discord_user_id,
            is_primary=is_primary,
        )

        # Remove pending code
        del _pending_codes[code]

        log(f"Linked Discord user {discord_user_id} to osu! user {osu_user_id}", Ansi.LGREEN)
        return True, "Successfully linked your osu! account!"

    async def unlink_account(
        self,
        osu_user_id: int,
        discord_user_id: int,
    ) -> tuple[bool, str]:
        """
        Unlink a Discord account from an osu! account.

        Args:
            osu_user_id: osu! user ID.
            discord_user_id: Discord user ID to unlink.

        Returns:
            Tuple of (success, message).
        """
        link = await discord_repositories.user.get_by_discord(discord_user_id)
        if not link or link["osu_user_id"] != osu_user_id:
            return False, "Account link not found."

        await discord_repositories.user.delete(link["id"])

        # If this was primary, set another as primary
        if link["is_primary"]:
            remaining = await discord_repositories.user.get_by_osu(osu_user_id)
            if remaining:
                await discord_repositories.user.set_primary(remaining[0]["id"], osu_user_id)

        return True, "Successfully unlinked your Discord account."

    async def get_linked_accounts(
        self,
        osu_user_id: int,
    ) -> list[dict[str, Any]]:
        """
        Get all linked Discord accounts for an osu! user.

        Args:
            osu_user_id: osu! user ID.

        Returns:
            List of linked account info.
        """
        return await discord_repositories.user.get_by_osu(osu_user_id)

    async def get_primary_discord(
        self,
        osu_user_id: int,
    ) -> int | None:
        """
        Get the primary Discord user ID for an osu! user.

        Args:
            osu_user_id: osu! user ID.

        Returns:
            Discord user ID or None.
        """
        primary = await discord_repositories.user.get_primary(osu_user_id)
        if primary:
            return primary["discord_user_id"]
        return None

    def _cleanup_expired_codes(self) -> None:
        """Remove expired pending codes."""
        current_time = time.time()
        expired = [
            code for code, data in _pending_codes.items()
            if current_time - data["created_at"] > self.CODE_EXPIRY
        ]
        for code in expired:
            del _pending_codes[code]


# Global instance
account_linking_service = AccountLinkingService()
```

## 2. In-Game Command

### 2.1 Add to `app/commands/categories/user.py` (or create new)

```python
"""Discord account linking commands."""

from __future__ import annotations

from app.discord.services.account_linking_service import account_linking_service
from app.commands.base import Command
from app.commands.context import CommandContext


@Command(
    name="link",
    aliases=["discord"],
    description="Link your Discord account",
    prefix="!",
)
async def link_command(ctx: CommandContext) -> None:
    """Handle the !link command in-game."""
    args = ctx.args

    if not args:
        # Generate a link code
        code = account_linking_service.generate_link_code(
            osu_user_id=ctx.player.id,
        )
        await ctx.respond(
            f"Your link code is: {code}\n"
            f"Use this code with the /link command in Discord.\n"
            f"Code expires in 10 minutes."
        )
        return

    code = args[0].upper()
    success, message = await account_linking_service.complete_link_from_osu(
        code=code,
        osu_user_id=ctx.player.id,
    )
    await ctx.respond(message)


@Command(
    name="unlink",
    description="Unlink a Discord account",
    prefix="!",
)
async def unlink_command(ctx: CommandContext) -> None:
    """Handle the !unlink command in-game."""
    args = ctx.args

    if not args:
        # Show linked accounts
        linked = await account_linking_service.get_linked_accounts(ctx.player.id)
        if not linked:
            await ctx.respond("You have no linked Discord accounts.")
            return

        accounts = []
        for link in linked:
            primary = " (Primary)" if link["is_primary"] else ""
            accounts.append(f"- Discord ID: {link['discord_user_id']}{primary}")

        await ctx.respond("Linked Discord accounts:\n" + "\n".join(accounts))
        return

    # Unlink specific Discord ID
    try:
        discord_id = int(args[0])
    except ValueError:
        await ctx.respond("Invalid Discord ID.")
        return

    success, message = await account_linking_service.unlink_account(
        osu_user_id=ctx.player.id,
        discord_user_id=discord_id,
    )
    await ctx.respond(message)
```

## 3. Discord Slash Command (Future)

### 3.1 `app/discord/commands/link_command.py` (For future implementation)

```python
"""Discord link command - for future implementation with Lightbulb."""

# This will be implemented when slash commands are added
# For now, the linking is done through DMs with the bot

# Example structure:
# @lightbulb.command("link", "Link your osu! account")
# @lightbulb.implements(lightbulb.SlashCommand)
# async def link_slash(ctx: lightbulb.Context) -> None:
#     # Generate code or complete link
#     pass
```

## 4. Commit Message

```
feat(discord): add account linking between osu! and Discord

- Implement AccountLinkingService with verification codes
- Add bidirectional linking (osu! → Discord, Discord → osu!)
- Add !link and !unlink in-game commands
- Support multiple Discord accounts per osu! account
- Add primary account designation
- Add 10-minute code expiry
```
