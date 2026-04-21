"""Token-aware context trimming for ollmcp.

Keeps conversations within the model's context window by trimming
oldest messages when the estimated token count exceeds the budget.
"""
from typing import List, Tuple


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: List[dict]) -> int:
    """Estimate total tokens for a messages list."""
    total = 0
    for msg in messages:
        content = msg.get("content") or ""
        if isinstance(content, str):
            total += estimate_tokens(content)
        # Account for tool_calls field overhead
        if msg.get("tool_calls"):
            total += 50
        total += 8  # message envelope overhead
    return total


def trim_messages_for_context(
    messages: List[dict],
    max_tokens: int = 8192,
    reserve_for_response: int = 1024,
    keep_last_n: int = 6,
) -> Tuple[List[dict], bool]:
    """Trim messages to fit within max_tokens budget.

    Strategy:
    - Always keep system message (if any)
    - Always keep the last keep_last_n messages
    - Remove oldest messages from the middle first

    Args:
        messages: Full message list
        max_tokens: Model context window size
        reserve_for_response: Tokens to reserve for model response
        keep_last_n: Minimum recent messages to always keep

    Returns:
        (trimmed_messages, was_trimmed)
    """
    budget = max_tokens - reserve_for_response
    if estimate_messages_tokens(messages) <= budget:
        return messages, False

    # Separate system prompt
    if messages and messages[0].get("role") == "system":
        system = [messages[0]]
        history = list(messages[1:])
    else:
        system = []
        history = list(messages)

    # Partition into trimmable (old) + must-keep (recent)
    if len(history) > keep_last_n:
        trimmable = history[:-keep_last_n]
        must_keep = history[-keep_last_n:]
    else:
        trimmable = []
        must_keep = history

    # Trim oldest entries until we fit
    while trimmable and estimate_messages_tokens(system + trimmable + must_keep) > budget:
        trimmable.pop(0)

    trimmed = system + trimmable + must_keep
    return trimmed, len(trimmed) < len(messages)
