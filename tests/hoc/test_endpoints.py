import pytest

from ldf.common.system.endpoints import HomeDeviceListEntry
from ldf.models.base import LawoHomeNativeDevice
from tests import log

pytestmark = [
    pytest.mark.dependency
]


def test_hoc_endpoints(hoc):
    for info in hoc.endpoints:
        log.info(f"{info}")
        assert isinstance(info, HomeDeviceListEntry)


@pytest.mark.parametrize(
    "test_filter",
    [
        {"model": ".edge", "state": "online"},
        {"model": "A__mic8", "state": "offline"},
        {"label": "A__mic8 - 1"},
        {"state": "online"},
        {"state": "offline"},
    ]
)
async def test_hoc_endpoints_filter(hoc, test_filter):

    for info in hoc.endpoints.filter(**test_filter):
        assert isinstance(info, HomeDeviceListEntry)
        log.info(f"{info}")


def test_hoc_create_native(hoc):
    device = hoc.endpoints.create_native('pPocT9R2gTFRnJWzSnVBBf')
    assert isinstance(device, LawoHomeNativeDevice)


async def test_hoc_create_natives(hoc):

    devices = await hoc.endpoints.create_natives(
        [dev.home_id for dev in hoc.endpoints]
    )

    for dev_id in devices:
        log.info(dev_id)
        try:
            assert isinstance(devices[dev_id], LawoHomeNativeDevice)
            assert devices[dev_id].id == dev_id
        except AssertionError:
            log.error(f"Failed to create device {dev_id} {devices[dev_id]}")

    log.info(f"Attempted: {len(hoc.endpoints)}")
    log.info(f"Created: {len(devices)}")


async def test_endpoints_sords(hoc):

    for sord in hoc.routes._sords:
        log.info(sord)
