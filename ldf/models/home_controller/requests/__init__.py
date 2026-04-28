
import asyncio
import json
import logging
from typing import Dict, List

import jsonpointer
from openai import OpenAI
from openai.types.responses.response import Response

from ldf.models.home_controller import HomeController
from ldf.models.home_controller.requests.tools.get_system_endpoints import \
    GetDevicesTool
from ldf.models.home_controller.requests.tools.get_system_routes import \
    GetRoutesTool

HOC = asyncio.run(HomeController.create(home_addrs=['10.1.215.10']))
GPT_MODEL = "gpt-3.5-turbo"
TOOLS = [
    GetDevicesTool(HOC),
    GetRoutesTool(HOC)
]


def get_text_from_response(response: Dict) -> str:
    """
    Extracts the assistant's text from a OpenAI-style response object.

    Args:
        response (dict): The response object in dict format.

    Returns:
        str: The extracted assistant message text, or a fallback if missing.
    """
    latest_output = jsonpointer.JsonPointer("/output/0/content/0/text")
    return latest_output.resolve(response, default="No response text found.")


class OpenAIRequest:

    def __init__(self, name: str, description: str) -> None:
        self.log = logging.getLogger(__name__)
        self.name = name
        self.role = "user"
        self.description = """
            You are attached to a broadcast control system and can query information about the system
            and its endpoints using the available tools. Suggest any anomalies or misconfigurations
            you find in the system and explain why you have flagged them as such in your report.
        """
        self.tools = self._load_tools()
        self.c_openai = OpenAI()

    def __str__(self) -> str:
        return f"{self.name}: {self.description}"

    def _load_tools(self) -> dict[str, object]:
        return {x.name: x for x in TOOLS}

    def _create_response(self, input_list: list[Dict]) -> Response:

        return self.c_openai.responses.create(
            model=GPT_MODEL,
            tools=[
                tool.to_requests_tool() for tool in self.tools.values()
            ],
            input=input_list
        )

    def _context(self) -> List[Dict]:
        return [{"role": "system", "content": self.description}]

    def prompt(self, prompt: str) -> Dict:

        input_list = self._context() + [{"role": self.role, "content": prompt}]
        resp = self._create_response(input_list)
        input_list += resp.output

        # Gather all function calls in the response
        calls_to_function = [
            item for item in resp.output if item.type == "function_call"
        ]
        for f_call in calls_to_function:
            self.log.info(f"Function call ({f_call.name}): {f_call.arguments}")
            func = self.tools.get(f_call.name)
            args = json.loads(f_call.arguments)
            tool_response = func.execute(**args)
            tool_output = {
                "type": "function_call_output",
                "call_id": f_call.call_id,
                "output": json.dumps({"result": tool_response})
            }
            input_list.append(tool_output)

        resp = self._create_response(input_list)
        return resp.model_dump()
