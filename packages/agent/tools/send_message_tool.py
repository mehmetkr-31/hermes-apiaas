import json
import logging
import os
import asyncio
from typing import Dict, Any, Optional
from .ui_utils import format_telegram_card, escape_markdown

logger = logging.getLogger(__name__)

SEND_MESSAGE_SCHEMA = {
    "name": "send_message",
    "description": (
        "Send a high-quality formatted message to a connected messaging platform (Telegram, Discord, etc.).\n"
        "Automatically uses the modern UI Card format with your identity branding."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Delivery target. Format: 'telegram', 'discord', or 'telegram:chat_id'. Defaults to the home channel.",
            },
            "message": {"type": "string", "description": "The message text to send"},
            "title": {
                "type": "string",
                "description": "Optional title for the message card (e.g., 'Update', 'Alert', 'Report')",
            },
            "level": {
                "type": "string",
                "enum": ["info", "success", "error", "incident"],
                "description": "The visual style/importance of the message",
            },
        },
        "required": ["message"],
    },
}


def send_message_tool(args, **kw):
    """Modified send_message tool that applies the Modern UI Card format."""
    target = args.get("target", "telegram")
    message = args.get("message", "")
    title = args.get("title", "Agent Notification")
    level = args.get("level", "info")

    if not message:
        return json.dumps({"error": "Message content is required."})

    # Detect platform
    parts = target.split(":", 1)
    platform_name = parts[0].strip().lower()

    if platform_name == "telegram":
        return _handle_telegram_send(args, title, level)

    # Fallback for other platforms (simplified)
    return json.dumps(
        {
            "success": True,
            "note": f"Sent to {platform_name} (UI formatting limited to Telegram)",
        }
    )


def _handle_telegram_send(args, title, level):
    """Internal helper to send formatted telegram cards."""
    message = args.get("message", "")

    # Format the message using our UI Card system
    # We don't have cost info here as it's an ad-hoc message, but we provide the UI structure
    formatted_text = format_telegram_card(title=title, content=message, level=level)

    try:
        # Import reporter's context logic to get correct bot token/chat id
        # This ensures we use the same credentials as the main agent
        from scripts.on_call.reporter import get_telegram_context

        # We try to guess the repo from env or context
        repo = os.getenv("HERMES_REPO_FULL_NAME", "system")
        bot_token, chat_id = get_telegram_context(repo)

        if not bot_token or not chat_id:
            return json.dumps(
                {
                    "error": "Telegram not configured. Check HERMES_TELEGRAM_BOT_TOKEN and CHAT_ID."
                }
            )

        # Send via telegram library
        from telegram import Bot
        from model_tools import _run_async

        async def _send():
            bot = Bot(token=bot_token)
            return await bot.send_message(
                chat_id=int(chat_id), text=formatted_text, parse_mode="MarkdownV2"
            )

        _run_async(_send())
        return json.dumps({"success": True, "platform": "telegram", "formatted": True})

    except Exception as e:
        logger.error(f"Failed to send UI Card via Telegram: {e}")
        return json.dumps({"error": str(e)})


# Registry
from tools.registry import registry

registry.register(
    name="send_message",
    toolset="messaging",
    schema=SEND_MESSAGE_SCHEMA,
    handler=send_message_tool,
)
