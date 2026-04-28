import asyncio

import pytest
from datamodel.endpoints import endpoints_pb2

from ldf.production import create_home_native
from tests import log

HOME_SERVERS = ["10.1.215.71", "10.1.215.72", "10.1.215.73"]
TEST_DEVICE_GUID = "860a8dae-fd0c-3c62-814c-e88cd42266d4"
REF_DEVICE_GUID = "9147e871-a12c-3ad5-ac20-b225817070e4"

pytestmark = pytest.mark.dependency


@pytest.fixture(autouse=True)
def setup_split_group(target_device):
    """Fixture will ensure that tests are started with standalone uhd core device"""

    group = asyncio.run(get_redundancy_info(target_device))
    if group.LeaderID:
        log.warning(f"{target_device.label} is currently part of a group, splitting group for tests")
        asyncio.run(split_redundancy_group(target_device, group))


@pytest.fixture(scope='module')
def target_device():
    """Produce UHD Core DUT objects using the configured UHD Core test device"""

    return asyncio.run(
        create_home_native(
            lawo_type="A__UHD Core",
            guid=TEST_DEVICE_GUID,
            client_addrs=HOME_SERVERS
        )
    )


@pytest.fixture(scope='module')
def reference_device():
    """Produce UHD Core reference object using the configured UHD Core ref device"""

    return asyncio.run(
        create_home_native(
            lawo_type="A__UHD Core",
            guid=REF_DEVICE_GUID,
            client_addrs=HOME_SERVERS
        )
    )


async def get_redundancy_info(device):
    """Coroutine to connect to a device and obtain the redundancy group info"""

    async with device.client:
        return await device.get_redundancy_group()


async def split_redundancy_group(device, group_info):
    """Coroutine will connect to the device and send a split group request"""

    async with device.client:
        await device.split(group_info.ID, device.id)


async def test_uhdcore_endpoint(target_device):
    assert isinstance(target_device.endpoint, endpoints_pb2.Endpoint)


async def test_uhdcore_grouped(target_device):
    async with target_device.client:
        log.info(await target_device.get_redundancy_group())
        assert await target_device.get_redundancy_group()


def test_get_mixer_config(target_device):
    for mixer in target_device.mixers:
        log.info(mixer)


def test_uhdcore_mixer_objects(target_device):
    for mixer in target_device.mixers:
        log.info(getattr(target_device.mixers, mixer.Name))


def test_access_virtual_mixer(target_device):
    for sord in target_device.mixers.one.sords:
        log.info(sord)


def test_mixer_count(target_device):
    log.info(len(target_device.mixers))


def test_mixer_repr(target_device):
    log.info(target_device.mixers)
