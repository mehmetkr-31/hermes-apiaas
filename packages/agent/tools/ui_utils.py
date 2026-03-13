import re
from typing import Optional, Dict, Any


def escape_markdown(text: str) -> str:
    """Helper to escape Telegram MarkdownV2 special characters."""
    if not text:
        return ""
    # Characters that must be escaped in MarkdownV2
    escape_chars = r"\_*[]()~`>#+-=|{}.!\\"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", str(text))


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
    header = f"*{icon} {escape_markdown(title.upper())}*"
    divider = "────────────────────"

    # Build Body
    body = f"\n{divider}\n"
    if repo_name:
        body += f"📂 *Repo:* `{escape_markdown(repo_name)}`\n\n"

    # Main message (italics for agent thoughts, normal for others)
    msg_prefix = "💬 *Response:*\n" if level == "info" or level == "agent" else ""
    body += f"{msg_prefix}_{escape_markdown(content)}_"

    # Build Footer (Cost & Tokens)
    footer = ""
    if cost is not None or tokens is not None:
        footer += f"\n{divider}\n"
        parts = []
        if cost is not None:
            # Format and then escape to handle the dot
            cost_str = escape_markdown(f"{cost:.4f}")
            parts.append(f"💰 *Cost:* `${cost_str}`")
        if tokens is not None:
            # Format and then escape to handle commas
            tokens_str = escape_markdown(f"{tokens:,}")
            parts.append(f"⚡ *Tokens:* `{tokens_str}`")
        # Escape the separator pipe
        footer += "  \\|  ".join(parts)

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
