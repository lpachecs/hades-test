import pytest
from datamodel.client.client import Client

from ldf.models._manifest import model_manifest
from ldf.models.base import LawoHomeNativeDevice
from ldf.models.home_controller import HomeController
from ldf.production import create_home_native
from tests import log

TARGET_SYSTEM = ["10.1.215.66"]

pytestmark = pytest.mark.dependency


@pytest.fixture(scope="class")
async def hoc():
    hoc = await HomeController.create(TARGET_SYSTEM)
    yield hoc
    await hoc.close()


@pytest.fixture(params=[x for x in model_manifest])
async def dev_info(request, hoc):
    try:
        return next(hoc.endpoints.filter(model=request.param, state='online'))
    except StopIteration:
        pytest.skip(
            f"No online endpoint of type {request.param} exists on the target system"
        )


class TestModelProduction:

    async def test_create_home_native_iso_client(self, dev_info):
        """Validate legacy method of creating all available LDF device types

        Test will create a standalone LDF device object with a self contained
        NATs client.
        """

        device = await create_home_native(
            lawo_type=dev_info.model,
            guid=dev_info.guid,
            client_addrs=TARGET_SYSTEM
        )
        assert isinstance(device, LawoHomeNativeDevice)

    async def test_create_home_native_ext_client(self, dev_info):
        """Validate passing an external NATs client to `create_home_native`

        Test will create a standalone external NATs client and pass that to
        the `create_home_native` method from ldf.production. Any device created
        using the `nats_client` argument will be created with the same external
        client.
        """

        client = Client(
            addr=TARGET_SYSTEM
        )

        device = await create_home_native(
            lawo_type=dev_info.model,
            guid=dev_info.guid,
            nats_client=client
        )
        assert device.client == client

    async def test_hoc_create_natives(self, hoc):
        devs = await hoc.endpoints.create_natives(
            [x.home_id for x in hoc.endpoints.filter(state='online')]
        )

        for dev in devs.values():
            assert hoc.conns.nats == dev.client
            log.info(f"{dev}")
            log.info(f"\t{dev.client} ({hoc.conns.nats})")

        log.info(f"Created {len(devs)} models")
