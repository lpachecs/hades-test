import pytest

from tests import log

pytestmark = [
    pytest.mark.dependency
]


async def test_list_all_device_controls(hoc):
    devices = await hoc.endpoints.create_natives([
        info.home_id for info in hoc.endpoints
    ])

    for device in devices.values():
        for key, ctl in device.controls().items():
            log.info(f"{device.label} | {key} | {ctl}")
