
import pytest

from ldf.models.base import LawoHomeNativeDevice
from tests import log

pytestmark = [
    pytest.mark.dependency
]


async def test_list_proxy_devices(hoc):
    for proxy in await hoc.endpoints.list_proxy_devices():
        log.info(proxy)


async def test_create_proxy_lifecycle(hoc):
    """Test the lifecycle of a Proxy device in HOME

    Includes validation of creation, detection in cache
    via appropriate update messages
    """

    # Create the device proxy registration
    # Wait for the device to appear in the chache via update
    proxy_label = "Test Proxy Device"
    dev_registration = await hoc.endpoints.create_proxy(
        label=proxy_label,
        device_type="third_party",
        ip_address="192.168.1.100",
        port=8080
    )

    # Create an LDF device object for the new proxy device
    dev_info = next(x for x in hoc.endpoints.filter(label=proxy_label))
    dev_model = await hoc.endpoints.create_natives([dev_info.home_id])
    assert isinstance(dev_model[dev_info.home_id], LawoHomeNativeDevice)

    # Remove the device proxy registration
    # Method will block until the device is removed from the hoc cache via update
    await hoc.endpoints.remove_proxies([dev_registration.ID])
    log.info("Removed proxy registration, wait for service shutdown...")

    # Purge the device from HOME
    # Func blocks until the device is removed from the hoc cache via update
    removed_ids = await hoc.endpoints.purge([dev_info.home_id])
    assert len(removed_ids) != 0
