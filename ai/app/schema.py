"""Turn a Pydantic JSON schema into the small subset both Gemini and Claude accept."""
from __future__ import annotations

from typing import Any

_DROP = {"title", "default", "additionalProperties", "$defs", "definitions", "examples", "$schema"}


def clean_schema(node: Any) -> Any:
    if isinstance(node, list):
        return [clean_schema(x) for x in node]
    if not isinstance(node, dict):
        return node
    # Optional[X] comes out as anyOf [X, null]; keep X.
    if "anyOf" in node:
        options = [o for o in node["anyOf"] if not (isinstance(o, dict) and o.get("type") == "null")]
        if len(options) == 1:
            merged = {**{k: v for k, v in node.items() if k != "anyOf"}, **options[0]}
            return clean_schema(merged)
    out = {}
    for key, value in node.items():
        if key in _DROP:
            continue
        # property names must survive even if one is called "title" or "default"
        if key == "properties" and isinstance(value, dict):
            out[key] = {name: clean_schema(sub) for name, sub in value.items()}
        else:
            out[key] = clean_schema(value)
    return out


def has_params(schema: dict | None) -> bool:
    return bool(schema and schema.get("properties"))
