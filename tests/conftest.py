import asyncio
import logging
from typing import Iterable

import pytest
from datamodel.sords import sords_pb2
from systemlink.common.m_lookup import MNumberLookup as MNumber

from ldf.models.base import LawoHomeNativeDevice
from ldf.models.mcx import LawoMCXDevice
from ldf.production import create_home_native
from tests.user_config import (HOME_SERVERS, MCX_IP_ADDRESS, MCX_USE_HOME,
                               REF_DEVICE_GUID, REF_DEVICE_TYPE,
                               TEST_DEVICES_GUIDS)

log = logging.getLogger(__name__)


@pytest.fixture
def test_mixer() -> LawoMCXDevice | LawoHomeNativeDevice:
    """Uses LDF to produce a Virtual Mixer slice used in all tests"""

    # Use local MCX instance without Home connection
    if MCX_USE_HOME is False:
        return LawoMCXDevice(home_connection=False)

    # Use MCX instance with Home connection
    if not TEST_DEVICES_GUIDS["mcx"]:
        pytest.skip("No Virtual Mixer available for testing")

    return asyncio.run(create_home_native(lawo_type="mcx", guid=TEST_DEVICES_GUIDS["mcx"], client_addrs=HOME_SERVERS))


@pytest.fixture
async def test_mixer_connected(test_mixer):
    # Use custom IP?!
    if MCX_USE_HOME is False and (MCX_IP_ADDRESS is None or MCX_IP_ADDRESS == ""):
        raise ValueError("MCX IP Address must be set if not using Home connection")

    await test_mixer.connect(host_address=MCX_IP_ADDRESS)

    yield test_mixer

    await test_mixer.wait_for(MNumber.SYSTEM_BLINK)  # To make sure all changes are applied and send
    await test_mixer.disconnect()


async def build_device(model: str, guid: str) -> LawoHomeNativeDevice:
    """Build the requested device using LawoDeviceFactory

    Args:
        model (str): The model of the requested device
        guid (str): GUID of the requested device

    Returns:
        LawoHomeNativeDevice: A populated device model of the requested device
    """

    return await create_home_native(lawo_type=model, guid=guid, client_addrs=HOME_SERVERS)


async def create_sords_and_wait(
    device: LawoHomeNativeDevice,
) -> tuple[Iterable[sords_pb2.Sord], Iterable[sords_pb2.Sord]]:
    """Create a preset number of sender and receiver sords on a device and wait for expected updates

    Args:
        device (LawoHomeNativeDevice): Device that the sords will be created on

    Returns:
        tuple[Iterable[sords_pb2.Sord], Iterable[sords_pb2.Sord]]: Tuple of messages for created (senders, receivers)
    """

    async with device:
        tasks = asyncio.gather(
            device.sords.create_audio(3, 8, direction="tx", label="HOME-automated-QA-sender"),
            device.sords.create_audio(6, 8, direction="rx", label="HOME-automated-QA-receiver"),
        )
        senders, receivers = await tasks
        return senders, receivers


async def clean_sords_and_wait(
    device: LawoHomeNativeDevice, senders: Iterable[sords_pb2.Sord], receivers: Iterable[sords_pb2.Sord]
) -> None:
    """Remove any sords created (usually during setup) and wait for the appropriate updates

    Args:
        device (LawoHomeNativeDevice): _description_
        senders (Iterable[sords_pb2.Sord]): _description_
        receivers (Iterable[sords_pb2.Sord]): _description_
    """

    async with device.client:
        await asyncio.gather(device.sords.remove(senders), device.sords.remove(receivers))

    for sender, receiver in zip(senders, receivers):
        while not sender.ID and receiver.ID not in [x.ID for x in device.sords()]:
            await asyncio.sleep(0.1)
            continue


@pytest.fixture
def home_servers():
    return HOME_SERVERS


@pytest.fixture(params=[x for x in TEST_DEVICES_GUIDS], ids=[x for x in TEST_DEVICES_GUIDS], scope="module")
def test_device_type(request):
    return request.param


@pytest.fixture(scope="module")
def test_device_guid(test_device_type):
    return TEST_DEVICES_GUIDS[test_device_type]


@pytest.fixture(scope="module")
def built_test_device(test_device_type, test_device_guid):
    return asyncio.run(build_device(model=test_device_type, guid=test_device_guid))


@pytest.fixture(scope="module")
def reference_device():
    return asyncio.run(build_device(model=REF_DEVICE_TYPE, guid=REF_DEVICE_GUID))


@pytest.fixture(scope="class")
def require_audio_sords_target(built_test_device):
    """Handles creation and post test removal of predefined sords on the target device for tests"""

    if built_test_device.model == ".edge":
        log.warning(f"Target device {built_test_device.label} does not support sord creation or removal")
        senders = built_test_device.sords(direction="tx", essence="audio")
        receivers = built_test_device.sords(direction="rx", essence="audio")
    else:
        senders, receivers = asyncio.run(
            create_sords_and_wait(built_test_device),
        )

    log.info(f"Created required target senders: {[x.ID for x in senders]}")
    log.info(f"Created required target receivers: {[x.ID for x in receivers]}")
    yield senders, receivers

    if built_test_device.model != ".edge":
        asyncio.run(clean_sords_and_wait(built_test_device, senders, receivers))


@pytest.fixture(scope="class")
def require_audio_sords_ref(reference_device):
    """Handles creation and post test removal of predefined sords on the reference device for tests"""

    try:
        reference_device.flags["CreateDeleteSords"]
        reference_device.flags["IsStreamer"]
    except KeyError:
        if not reference_device.model == ".edge":
            pytest.skip(f"Target device {reference_device.label} does not support sord creation or removal")

    if reference_device.model == ".edge":
        senders = reference_device.sords(direction="tx", essence="audio")
        receivers = reference_device.sords(direction="rx", essence="audio")
    else:
        senders, receivers = asyncio.run(
            create_sords_and_wait(reference_device),
        )

    log.info(f"Created required reference senders: {[x.ID for x in senders]}")
    log.info(f"Created required reference receivers: {[x.ID for x in receivers]}")
    yield senders, receivers

    if reference_device.model != ".edge":
        asyncio.run(clean_sords_and_wait(reference_device, senders, receivers))
