import time

import pytest
from datamodel.endpoints import endpoints_pb2

from tests import log

TEST_IP_ADDR = "1.1.1.1"
TEST_LABEL = "LDF Interface Test Label"

pytestmark = pytest.mark.dependency


@pytest.fixture
def test_interface(built_test_device):
    """Fixture will provide the last device interface (sorted by ID) for testing"""

    test_int = [i for i in built_test_device.interfaces()][-1]
    log.info(f"Interface used for test: {test_int.Label}")
    return test_int


async def test_get_device_interfaces(built_test_device):
    """Validate that the ldf model interface.get() func returns correctly"""

    async with built_test_device.client:
        interfaces = built_test_device.interfaces()

    for int in interfaces:
        log.info(int)


async def test_iterate_interfaces(built_test_device):
    """Validate device interfaces can be correctly iterated over without connection"""

    for int in built_test_device.interfaces:
        log.info((int.Label, int.IpAddress))
        assert isinstance(endpoints_pb2.NetworkInterface, int)


async def test_set_device_interface_ip(built_test_device, test_interface):
    """Test will validate the setting of an interface Ip address using set.networks"""

    log.info(f"Modify IP address: \
             Interface: {test_interface.Label} > {TEST_IP_ADDR}")

    pre_test_value = test_interface.IpAddress
    test_interface.IpAddress = TEST_IP_ADDR

    async with built_test_device.client:

        # Set modified interface value and validate return type
        for modified_int in await built_test_device.interfaces.set(
            [test_interface]
        ):
            assert modified_int == test_interface.ID

        time.sleep(5)

        try:
            for valid_int in await built_test_device.interfaces.get():
                if not valid_int.Label == test_interface.Label:
                    continue
                assert valid_int.IpAddress == TEST_IP_ADDR
        except AssertionError as err:
            raise err
        finally:
            test_interface.IpAddress = pre_test_value
            await built_test_device.interfaces.set([test_interface])


async def test_set_device_interface_label(built_test_device, test_interface):

    log.info(f"Modify Label: \
             Interface: {test_interface.Label} > {TEST_LABEL}")

    pre_test_value = test_interface.Label
    test_interface.Label = TEST_LABEL

    async with built_test_device.client:

        # Set modified interface value and validate return type
        for modified_int in await built_test_device.interfaces.set(
            [test_interface]
        ):
            assert modified_int == test_interface.ID

        time.sleep(5)

        try:
            for valid_int in await built_test_device.interfaces.get():
                if not valid_int.IpAddress == test_interface.IpAddress:
                    continue
                assert valid_int.Label == TEST_LABEL
        except AssertionError as err:
            raise err
        finally:
            test_interface.IpAddress = pre_test_value
            await built_test_device.interfaces.set([test_interface])
