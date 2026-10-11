"""Provider-neutral types used by the agent loop."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class AssistantTurn:
    text: str
    tool_calls: list[ToolCall]
    raw: Any  # provider-native message, replayed verbatim into the history
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ToolResultItem:
    call: ToolCall
    payload: dict  # {"ok": bool, "result"/"error": ...}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, turn: AssistantTurn) -> None:
        self.input_tokens += turn.input_tokens
        self.output_tokens += turn.output_tokens
