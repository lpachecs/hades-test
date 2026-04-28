from ldf.models.home_controller.requests.tools.base import BaseTool


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

    def execute(self):
        return self.hoc.endpoints.to_dict()
