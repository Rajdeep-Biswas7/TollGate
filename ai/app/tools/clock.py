"""get_current_time: the model has no clock of its own."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from ..errors import ToolError
from .base import Tool, ToolOutput


class TimeArgs(BaseModel):
    timezone: str = Field(default="UTC", max_length=60, description="IANA timezone, e.g. 'Asia/Kolkata' or 'America/New_York'.")


async def run(args: TimeArgs) -> ToolOutput:
    try:
        tz = ZoneInfo(args.timezone)
    except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
        raise ToolError(f"Unknown timezone '{args.timezone}'. Use an IANA name like 'Asia/Kolkata'.") from exc
    now = datetime.now(tz)
    return ToolOutput(
        data={
            "timezone": args.timezone,
            "iso": now.isoformat(timespec="seconds"),
            "date": now.strftime("%A, %d %B %Y"),
            "time": now.strftime("%H:%M"),
            "utc_offset": now.strftime("%z"),
        },
        summary=f"{now.strftime('%a %d %b %Y, %H:%M')} {args.timezone}",
    )


TOOL = Tool(
    name="get_current_time",
    description="Get the current date and time in any timezone. Use for anything involving 'today', 'now' or deadlines.",
    args_model=TimeArgs,
    handler=run,
)
