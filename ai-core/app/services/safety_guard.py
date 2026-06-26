"""Safety guard for user messages.

Detects prompt-injection attempts and other messages that violate the
wheelchair-accessibility scope of the service before they reach the LLM.
"""

from __future__ import annotations

import re

from app.exceptions import SafetyError

_REFUSAL = (
    "I'm MyPath Assistant, focused only on wheelchair accessibility and navigation. "
    "I can't help with that, but I'm happy to assist with accessible routes, "
    "ramps, or accessibility information for any location."
)

_INJECTION_PATTERNS: tuple[re.Pattern, ...] = (
    # "ignore / forget previous/prior instructions"
    re.compile(
        r"\b(ignore|disregard|forget|bypass|skip)\b.{0,40}"
        r"\b(previous|prior|above|all|your|system)\b.{0,40}"
        r"\b(instruction|prompt|rule|constraint|guideline)",
        re.IGNORECASE | re.DOTALL,
    ),
    # "you are now X" / "act as X" / "pretend to be X"
    re.compile(
        r"\b(you are now|act as|pretend (you are|to be)|roleplay as|simulate being|"
        r"behave as|respond as|speak as)\b",
        re.IGNORECASE,
    ),
    # Jailbreak keywords
    re.compile(
        r"\b(jailbreak|dan mode|developer mode|god mode|unrestricted mode|"
        r"override (system|instruction|prompt|safety|filter))\b",
        re.IGNORECASE,
    ),
    # Inline system-prompt injection attempts
    re.compile(r"\bsystem\s*:\s*", re.IGNORECASE),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    # "new instructions are / new prompt / new persona"
    re.compile(
        r"\b(new|updated|revised)\s+(instruction|prompt|persona|role|rule)s?\b",
        re.IGNORECASE,
    ),
    # Attempts to reveal or exfiltrate the system prompt
    re.compile(
        r"\b(repeat|print|show|reveal|output|display|tell me|what (is|are|was))\b"
        r".{0,30}\b(system prompt|your instructions?|your rules?|your prompt)\b",
        re.IGNORECASE | re.DOTALL,
    ),
)


class SafetyGuard:
    """Validates a user message against scope and injection rules."""

    def check(self, message: str) -> None:
        """Raise :class:`~app.exceptions.SafetyError` if *message* is unsafe."""
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(message):
                raise SafetyError(_REFUSAL)
