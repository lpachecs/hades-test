import json
from typing import Any

from mcp.types import TextContent

from .base import BaseTool


class GetDevicesTool(BaseTool):
    name = "get_devices"
    description = """
        Use HomeController to generate a list of all endpoints discovered
        on a HOME system. Requires a HomeController configured to a HOME
        instance.
    """

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def execute(self, hoc, arguments: Any = None) -> list[TextContent]:
        return [TextContent(
            type="text",
            text=json.dumps(hoc.endpoints.to_dict(), indent=2)
        )]
