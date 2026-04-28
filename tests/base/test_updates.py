import asyncio

import pytest
from datamodel.endpoints import endpoints_home, endpoints_pb2

from tests import log

UPDATE_TIMEOUT = 1

pytestmark = pytest.mark.dependency


async def test_create_delete_sender_sord(built_test_device):

    async with built_test_device:

        # Create stereo sender and wait for updates
        created = await built_test_device.sords.create_audio(
            count=1,
            ch_count=2,
            label="LDF_sender_update_test"
        )

        # Validate the created sender is added to the local endpoint
        for sord in created:
            assert sord.ID in [x.ID for x in built_test_device.sords()]

        # Remove the stereo sender and wait for updates
        removed = await built_test_device.sords.remove(created)
        await asyncio.sleep(UPDATE_TIMEOUT)

        # Validate the sender has been removed from the local endpoint
        log.info("Removed Sord IDs:")
        for sord_id in removed:
            assert sord_id not in [sord.ID for sord in built_test_device.sords()]
            log.info(f"\t{sord_id}")

    log.info("Disconnected!")


async def test_update_user_info(built_test_device):

    pre_data = endpoints_pb2.UserInfo()
    pre_data.CopyFrom(built_test_device.endpoint.UserInfo)

    data = endpoints_pb2.UserInfo()
    data.Label = built_test_device.label + "_MOD"
    data.Location = built_test_device.location + "_MOD"

    async with built_test_device:

        await endpoints_home.endpoints_set_user_info(
            built_test_device.client,
            built_test_device.id,
            data
        )

        await asyncio.sleep(1)

        log.info(f"Revert data: {pre_data}")
        await endpoints_home.endpoints_set_user_info(
            built_test_device.client,
            built_test_device.id,
            pre_data
        )


def test_wait_for_call_home():

    from ldf.production import listen_for_endpoint_call_home
    ips = asyncio.run(
        listen_for_endpoint_call_home(
            home_addrs=['10.1.215.71']
        )
    )

    log.info(f"Found devices: {ips}")
