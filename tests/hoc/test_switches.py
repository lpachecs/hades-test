import pytest

from ldf.attributes.interfaces import HomeControllerInterface
from ldf.common.system.endpoints import HomeDeviceListEntry
from ldf.models.switch import LawoHomeNetworkSwitch
from tests import log

pytestmark = [
    pytest.mark.dependency
]


@pytest.fixture
async def switch_devices(hoc) -> dict[str, HomeDeviceListEntry]:
    switch_ids = [sw.home_id for sw in hoc.endpoints.switch.values()]
    return await hoc.endpoints.create_natives(switch_ids)


async def test_hoc_get_switches(hoc, switch_devices):
    for switch_device in switch_devices.values():
        log.info(switch_device)
        assert isinstance(switch_device, LawoHomeNetworkSwitch)


async def test_hoc_switches_get_interfaces(switch_devices):

    for device in switch_devices.values():
        for iface in device.interfaces:
            log.info(f"{device.label} | {iface}")
            assert isinstance(iface, HomeControllerInterface)


async def test_hoc_switches_get_terminals(switch_devices):

    for device in switch_devices.values():
        async with device:
            stitches = await device.get_stitches()
            log.info(device.label)
            for stitch in stitches:
                log.info(f"\t {stitch}")
            # for term in device.terminals():
            #     log.info(f"{device.label} | {term}")
                # assert term.device_id == device.id


async def test_switch_traffic(switch_devices):

    for switch_device in switch_devices.values():
        async with switch_device:
            traffic = await switch_device.get_traffic([x.home_id for x in switch_device.interfaces])
            for t in traffic:
                log.info(t)


def test_switch_stitches(hoc):

    for route in hoc.routes:
        # assert isinstance(route, LawoHomeNativeDevice)
        for stitch in route.path_pri:
            log.info(f"{route}: {stitch}")
