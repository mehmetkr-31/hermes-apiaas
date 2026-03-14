import re
from typing import Optional, Dict, Any


def escape_html(text: str) -> str:
    """Helper to escape HTML special characters for Telegram."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def format_telegram_card(
    title: str,
    content: str,
    repo_name: Optional[str] = None,
    cost: Optional[float] = None,
    tokens: Optional[int] = None,
    level: str = "info",
) -> str:
    """Formats a message into a structured Telegram 'Card'."""

    # Emoji based on level
    icons = {
        "info": "🤖",
        "agent": "🧠",
        "tool": "🛠",
        "success": "✅",
        "error": "🚨",
        "incident": "⚠️",
    }
    icon = icons.get(level, "🤖")

    # Build Header
    header = f"<b>{icon} {escape_html(title.upper())}</b>"
    divider = "────────────────────"

    # Build Body
    body = f"\n{divider}\n"
    if repo_name:
        body += f"📂 <b>Repo:</b> <code>{escape_html(repo_name)}</code>\n\n"

    # Main message (italics for agent thoughts, normal for others)
    msg_prefix = "💬 <b>Response:</b>\n" if level == "info" or level == "agent" else ""
    body += f"{msg_prefix}<i>{escape_html(content)}</i>"

    # Build Footer (Cost & Tokens)
    footer = ""
    if cost is not None or tokens is not None:
        footer += f"\n{divider}\n"
        parts = []
        if cost is not None:
            parts.append(f"💰 <b>Cost:</b> <code>${escape_html(f'{cost:.4f}')}</code>")
        if tokens is not None:
            parts.append(f"⚡ <b>Tokens:</b> <code>{escape_html(f'{tokens:,}')}</code>")
        footer += "  |  ".join(parts)

    return f"{header}{body}{footer}"


def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model_id: str,
    metadata_cache: Dict[str, Any],
) -> float:
    """Calculates the USD cost based on token usage and model metadata."""
    if model_id not in metadata_cache:
        # Default fallback pricing (approximate Claude 3.5 Sonnet)
        input_price = 3.0 / 1_000_000
        output_price = 15.0 / 1_000_000
    else:
        pricing = metadata_cache[model_id].get("pricing", {})
        # OpenRouter provides pricing as strings or floats per 1k or 1m tokens
        # Standardizing to price per 1 token
        input_price = float(pricing.get("prompt", 0))
        output_price = float(pricing.get("completion", 0))

    return (prompt_tokens * input_price) + (completion_tokens * output_price)
