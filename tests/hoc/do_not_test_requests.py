import pytest

from ldf.models.home_controller.requests import OpenAIRequest as Agent
from ldf.models.home_controller.requests import get_text_from_response
from tests import log

pytestmark = [
    pytest.mark.dependency
]


@pytest.fixture
def agent():
    return Agent(
        name="Test HOME System Endpoints",
        description="Act to validate this collection of network endpoints"
    )


prompts = {
    "endpoints-by-device-type": "List all endpoints on the system. Show device labels and group them by device type",
    "endpoints-list-all-details": "List all endpoints on the system. Show all details available",
    "endpoints-list-all-online": "List all endpoints on the system that are online. Show all details available",
    "endpoints-list-all-offline": "List all endpoints on the system that are offline. Show all details available",
    "endpoints-count-device": "Count all types of devices on the system, list the counts and types only",
    "routes-active": "List all active routes on the system. Show all details available",
    "routes-unhealthy": "List all unhealthy routes on the system. Show all details available",
}


@pytest.mark.parametrize("prompt", prompts.values(), ids=prompts.keys())
def test_hoc_requests_tools_prompt(agent, prompt):
    """Use HomeController to make a request to the OpenAI API
    Suggest it makes use of the get_devices tool to list all endpoints"""

    response = agent.prompt(prompt)
    log.info(get_text_from_response(response))
