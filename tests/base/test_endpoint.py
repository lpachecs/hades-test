from asyncio import sleep

import pytest
from datamodel.endpoints import endpoints_home, endpoints_pb2

from tests import log

TEST_LABEL = "QA TEST LABEL"

pytestmark = pytest.mark.dependency


@pytest.mark.skip("Validation test")
async def test_endpoint_subscription(built_test_device):
    """Subscribe for device updates and sit on the subscription for x seconds"""

    async with built_test_device:
        await sleep(15)
    log.info(built_test_device.endpoint)


async def test_heartbeat_subscription(built_test_device):
    """Validate the wait_for_heartbeats function. Stall test untill 3 x heartbeats are received from the device"""

    async with built_test_device:
        await built_test_device.wait_for_heartbeats()


async def test_heartbeat_subscription_w_timeout(built_test_device):
    """Validate the wait_for_heartbeats function. Stall test untill 3 x heartbeats are received from the device"""

    async with built_test_device:
        await sleep(4)
        await built_test_device.wait_for_heartbeats(timeout=4)


def test_get_endpoint(built_test_device):
    """Validate the device endpoint data type"""

    log.info(built_test_device.endpoint)
    assert isinstance(built_test_device.endpoint, endpoints_pb2.Endpoint)


def test_get_endpoint_flags(built_test_device):
    log.info(built_test_device.flags)
    assert isinstance(built_test_device.flags, dict)


def test_get_id(built_test_device):
    """Validate call to `id` attribute of test device"""

    log.info(built_test_device.id)
    assert isinstance(built_test_device.id, str)


def test_get_guid(built_test_device):
    """Validate call to `GUID` attribute of test device"""

    log.info(built_test_device.endpoint.GUID)
    assert isinstance(built_test_device.endpoint.GUID, str)


def test_get_label(built_test_device):
    """Validate call to `label` attribute of test device"""

    log.info(built_test_device.label)
    assert isinstance(built_test_device.label, str)


async def test_set_endpoint_label(built_test_device):
    """Validate setting of the test device label"""

    async with built_test_device:
        log.info(f"Modify {built_test_device.label} device label")
        built_test_device.label = TEST_LABEL
        await endpoints_home.endpoints_set_user_info(
            built_test_device.client,
            built_test_device.id,
            built_test_device.endpoint.UserInfo
        )
        assert built_test_device.label == TEST_LABEL


def test_get_location(built_test_device):
    """Validate call to `location` attribute of test device"""

    log.info(built_test_device.location)
    assert isinstance(built_test_device.location, str)


def test_get_application(built_test_device):
    """Validate call to `application` attribute of test device"""

    log.info(built_test_device.application)
    assert isinstance(built_test_device.application, endpoints_pb2.Option)


def test_get_options(built_test_device):
    """Validate call to `options` attribute of test device"""

    for opt in built_test_device.options:
        log.info(opt)
        assert isinstance(opt, endpoints_pb2.Option)
