"""calculator: exact arithmetic so the model never does maths in its head."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..mathx import calculate
from .base import Tool, ToolOutput


class CalcArgs(BaseModel):
    expression: str = Field(
        min_length=1,
        max_length=200,
        description="Maths expression, e.g. '(1250 * 1.18) / 12' or 'sqrt(2) ** 10'. Supports + - * / // % ** and sqrt, ln, log10, sin, cos...",
    )


async def run(args: CalcArgs) -> ToolOutput:
    result = calculate(args.expression)
    return ToolOutput(
        data={"expression": args.expression, "result": result},
        summary=f"{args.expression} = {result}",
    )


TOOL = Tool(
    name="calculator",
    description="Evaluate a maths expression exactly. Always use this for arithmetic, percentages, unit maths and conversions.",
    args_model=CalcArgs,
    handler=run,
)
