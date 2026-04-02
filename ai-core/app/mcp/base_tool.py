"""Abstract base class for MCP tools.

To add a new tool:
  1. Subclass :class:`BaseTool`.
  2. Implement :attr:`name`, :attr:`declaration`, and :meth:`execute`.
  3. Register an instance with :class:`~app.mcp.server.MCPServer`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseTool(ABC):
    """Common interface every MCP tool must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier used by the model to invoke this tool."""

    @property
    @abstractmethod
    def declaration(self) -> dict:
        """Function-declaration schema passed to the LLM provider."""

    @abstractmethod
    def execute(self, args: dict) -> dict:
        """Execute the tool with the given arguments and return a JSON-serialisable dict."""
