import asyncio

import pytest

from ldf.models.home_controller import HomeController
from tests import log

pytestmark = pytest.mark.dependency


async def test_init_hoc():
    hoc = await HomeController.create(home_addrs=['10.1.215.71'])
    log.info(hoc)
    log.info(hoc._subscription_task)
    await asyncio.sleep(3)
    assert isinstance(hoc, HomeController)
    await hoc.close()
