import asyncio

import pytest

from ldf.models.home_controller import HomeController
from tests.user_config import HOME_SERVERS


@pytest.fixture
async def hoc():
    hoc = await HomeController.create(home_addrs=HOME_SERVERS)
    await asyncio.sleep(.25)  # Allow time for subscriptions to be established
    yield hoc
    await hoc.close()


def switch_device(request, hoc):

    for switch in hoc.endpoints.switch.values():
        return switch
