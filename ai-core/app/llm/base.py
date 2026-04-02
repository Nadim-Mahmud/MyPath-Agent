"""Abstract base class for LLM providers.

To add a new LLM provider (e.g. OpenAI, Anthropic):
  1. Subclass :class:`LLMProvider`.
  2. Implement :meth:`complete` and the :attr:`tool_declarations` property.
  3. Wire the new provider up in ``app/dependencies.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.llm.types import CompletionResult


class LLMProvider(ABC):
    """Common interface for language-model completion providers."""

    @abstractmethod
    def complete(self, user_message: str, history: list[dict]) -> CompletionResult:
        """Run a completion and return a structured result.

        Args:
            user_message: The (possibly enriched) user turn to send to the model.
            history:       Conversation history in the provider's native message format.

        Returns:
            A :class:`CompletionResult` containing the reply text and any
            extracted structured data (route action, map pins).
        """

    @property
    @abstractmethod
    def tool_declarations(self) -> list[dict]:
        """Return the list of tool/function declarations to pass to the model."""
