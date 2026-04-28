import json

from mcp.types import TextContent

from ldf.models.home_controller.mcp._tools.base import BaseTool


class GetRoutesTool(BaseTool):
    name = "get_routes"
    description = """
        Use API to generate a list of all network routes discovered
        on the system.
    """

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def execute(self, hoc, arguments: dict = None) -> list[TextContent]:
        return [TextContent(
            type="text",
            text=json.dumps(hoc.routes.to_dict(), indent=2)
        )]
