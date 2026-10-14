"""Small, deterministic language checks for learner-facing model output."""

from __future__ import annotations

import re


def matches_requested_language(text: str, language: str) -> bool:
    """Return whether a response visibly follows the selected UI language.

    Hindi and Hinglish are both promised with Devanagari in the interface prompts.
    This check is intentionally simple: it catches the common local-model failure
    where the model acknowledges the instruction but still answers only in English.
    """
    if language == "english":
        return True
    devanagari = len(re.findall(r"[\u0900-\u097f]", text))
    letters = max(1, len(re.findall(r"[A-Za-z\u0900-\u097f]", text)))
    minimum_ratio = 0.08 if language == "hinglish" else 0.20
    return devanagari >= 6 and devanagari / letters >= minimum_ratio


def rewrite_prompt(text: str, language: str) -> str:
    instruction = {
        "hindi": (
            "Rewrite the learner-facing text below in natural Hindi using Devanagari. "
            "Keep necessary technical terms in English."
        ),
        "hinglish": (
            "Rewrite the learner-facing text below in natural conversational Hinglish, "
            "using Devanagari Hindi mixed with familiar English technical terms."
        ),
    }[language]
    return f"""{instruction}
Preserve every fact, equation, heading and source-grounding boundary. Do not add new knowledge.
Return only the rewritten lesson, with clean Markdown and readable Unicode mathematics.

TEXT TO REWRITE:
{text}
"""
