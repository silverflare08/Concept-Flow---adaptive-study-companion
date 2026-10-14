"""Small, deterministic language checks for learner-facing model output."""

from __future__ import annotations

import re

HINGLISH_INSTRUCTION = (
    "Write in simple conversational Hinglish (Romanised Hindi), like a WhatsApp explanation. "
    "Simple Hinglish mein jawab do. Hindi ko English letters mein likho, aur technical terms "
    "English mein rakho. Do not use Devanagari script or answer entirely in English. "
    "Style example only, not course evidence: 'Standardisation se features ka scale comparable ho jata hai.'"
)


def matches_requested_language(text: str, language: str) -> bool:
    """Return whether a response visibly follows the selected UI language.

    Hindi uses Devanagari; Hinglish uses Romanised Hindi with English terms.
    This check is intentionally simple: it catches the common local-model failure
    where the model acknowledges the instruction but still answers only in English.
    """
    if language == "english":
        return True
    devanagari = len(re.findall(r"[\u0900-\u097f]", text))
    if language == "hinglish":
        words = set(re.findall(r"[a-z]+", text.casefold()))
        hindi_markers = {"hai", "hain", "ka", "ki", "ke", "mein", "nahi", "nahin", "samjho",
                         "karo", "hota", "hoti", "hote", "isse", "liye", "hum", "aap", "yeh",
                         "ye", "aur", "se", "ko", "toh", "karta", "karti", "kya", "chahiye"}
        return devanagari == 0 and len(words & hindi_markers) >= 2
    letters = max(1, len(re.findall(r"[A-Za-z\u0900-\u097f]", text)))
    minimum_ratio = 0.20
    return devanagari >= 6 and devanagari / letters >= minimum_ratio


def rewrite_prompt(text: str, language: str) -> str:
    instruction = {
        "hindi": (
            "Rewrite the learner-facing text below in natural Hindi using Devanagari. "
            "Keep necessary technical terms in English."
        ),
        "hinglish": "Rewrite the learner-facing text below. " + HINGLISH_INSTRUCTION,
    }[language]
    return f"""{instruction}
Preserve every fact, equation, heading and source-grounding boundary. Do not add new knowledge.
Return only the rewritten lesson, with clean Markdown and readable Unicode mathematics.

TEXT TO REWRITE:
{text}
"""
