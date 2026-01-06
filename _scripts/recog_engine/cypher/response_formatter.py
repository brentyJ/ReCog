"""
Cypher Response Formatter
Ensures all responses match Cypher's voice/personality
"""

import json
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Patterns that indicate non-Cypher style
BAD_PATTERNS = [
    r"\bi'm\b",
    r"\bi am\b",
    r"\bi'd be\b",
    r"\bi would\b",
    r"\bsorry\b",
    r"\bapologi",
    r"\bgreat question\b",
    r"\blet me think\b",
    r"\bhmm\b",
    r"\bhappy to help\b",
    r"\bexcited\b",
    r"\bwonderful\b",
    r"\bfascinating\b",
    r"\binteresting\b",
    r"\bconcerning\b",
    r"\bworrying\b",
    r"[!]{2,}",  # Multiple exclamation marks
    r"[:;]-?[)D]",  # Emoticons
]


def is_cypher_style(text: str) -> bool:
    """
    Check if response already follows Cypher's pattern.
    Returns True if text appears to match Cypher voice.
    """
    text_lower = text.lower()

    # Check for bad patterns
    for pattern in BAD_PATTERNS:
        if re.search(pattern, text_lower):
            return False

    # Good signs: starts with action verbs, contains numbers
    good_signs = [
        text[0].isupper(),  # Starts with capital
        len(text) < 300,  # Reasonably brief
        any(char.isdigit() for char in text),  # Contains numbers
    ]

    # Good starting words
    good_starts = [
        "acknowledged", "noted", "processing", "extracted", "detected",
        "filtered", "displaying", "entity", "pattern", "timeline",
        "removed", "added", "complete", "queued", "found",
    ]

    starts_well = any(text_lower.startswith(word) for word in good_starts)

    return starts_well or sum(good_signs) >= 2


def format_cypher_response(
    intent: str,
    result: Dict[str, Any],
    context: Dict[str, Any],
    anthropic_client=None
) -> Dict[str, Any]:
    """
    Ensures all responses match Cypher's voice/personality.
    Uses LLM to rewrite responses if needed.

    Args:
        intent: The classified intent
        result: The action router result dict
        context: Session context
        anthropic_client: Optional Anthropic client for LLM rewriting

    Returns:
        Result dict with reply potentially rewritten in Cypher voice
    """
    reply = result.get("reply", "")

    # If response already follows Cypher pattern, return as-is
    if is_cypher_style(reply):
        return result

    # No LLM available, try simple cleanup
    if not anthropic_client:
        result["reply"] = _simple_cleanup(reply)
        return result

    # Use LLM to rewrite in Cypher voice
    try:
        rewritten = _llm_rewrite(reply, context, anthropic_client)
        if rewritten:
            result["reply"] = rewritten
    except Exception as e:
        logger.error(f"LLM rewrite failed: {e}")
        result["reply"] = _simple_cleanup(reply)

    return result


def _simple_cleanup(text: str) -> str:
    """
    Simple cleanup to make text more Cypher-like without LLM.
    """
    # Remove common filler phrases
    fillers = [
        r"^(i'm |i am |i'd be |i would )",
        r"^(well,? |so,? |okay,? |alright,? )",
        r"^(let me |just a moment |one second )",
        r"(\.? ?is there anything else.*?\??)$",
        r"(\.? ?how can i help.*?\??)$",
    ]

    result = text
    for filler in fillers:
        result = re.sub(filler, "", result, flags=re.IGNORECASE)

    # Ensure it starts with capital
    result = result.strip()
    if result and result[0].islower():
        result = result[0].upper() + result[1:]

    return result


def _llm_rewrite(reply: str, context: Dict[str, Any], anthropic_client) -> Optional[str]:
    """
    Use LLM to rewrite response in Cypher voice.
    """
    from .prompts import load_cypher_system_prompt

    cypher_prompt = load_cypher_system_prompt(context)

    rewrite_request = f"""Rewrite this response in Cypher's voice:

Original: {reply}

Remember Cypher's pattern: [Observation/Status] + [Data/Evidence] + [Optional: Suggestion/Question]
Be precise, economical, terminal-style. No apologies. No filler. Lead with facts.

Rewrite only - respond with just the rewritten text, nothing else:"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=200,
        system=cypher_prompt,
        messages=[{"role": "user", "content": rewrite_request}]
    )

    rewritten = response.content[0].text.strip()

    # Sanity check - don't use if it's too different or weird
    if len(rewritten) > len(reply) * 2:
        logger.warning("LLM rewrite too long, using original")
        return None

    return rewritten


def format_processing_update(
    current: int,
    total: int,
    doc_name: str,
    events: list = None
) -> str:
    """
    Format a processing progress update in Cypher style.

    Args:
        current: Current document number
        total: Total documents
        doc_name: Current document name
        events: Optional list of events from this document

    Returns:
        Formatted progress message
    """
    lines = [f"Doc {current}/{total}: {doc_name}"]

    if events:
        for event in events[:3]:  # Max 3 events
            lines.append(f"  - {event}")

    return "\n".join(lines)


def format_completion_message(
    insights_count: int,
    entities_count: int,
    patterns_count: int = 0,
    case_title: str = None
) -> str:
    """
    Format a processing completion message in Cypher style.
    """
    parts = [
        "Processing complete.",
        f"{insights_count} insights extracted.",
        f"{entities_count} entities identified.",
    ]

    if patterns_count > 0:
        parts.append(f"{patterns_count} patterns detected.")

    parts.append("Review findings?")

    return " ".join(parts)


def format_error_message(error_type: str, details: str = None) -> str:
    """
    Format an error message in Cypher style (brief, no apologies).
    """
    messages = {
        "network": "Connection failed. Retry?",
        "timeout": "Request timed out. Retry?",
        "not_found": "Resource not found. Check input.",
        "permission": "Access denied. Check permissions.",
        "validation": f"Invalid input. {details or 'Check format.'}",
        "server": "Server error. Logged for review.",
        "unknown": "Operation failed. Error logged.",
    }

    return messages.get(error_type, messages["unknown"])
