from ldf.models.home_controller.requests.tools.base import BaseTool


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

    def execute(self, arguments: dict) -> list[dict]:
        return self.hoc.routes.to_dict()
