"""Exception types shared across the AI service."""
from __future__ import annotations


class LLMError(Exception):
    """A problem talking to the language model (bad key, quota, empty reply...)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ToolError(Exception):
    """An expected tool failure. The message is shown to the model so it can recover."""
