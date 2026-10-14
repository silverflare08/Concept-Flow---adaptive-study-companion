"""Conservative quality checks, not semantic or mathematical verification."""
import re


def has_runaway_repetition(text: str) -> bool:
    words = re.findall(r"\w+", text.casefold())
    phrases = [tuple(words[i:i + 12]) for i in range(0, len(words) - 11, 12)]
    return len(phrases) >= 12 and len(set(phrases)) / len(phrases) <= 0.5
