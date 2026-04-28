import asyncio

import pytest

from ldf.common.connections import connect_sords, disconnect_destinations
from ldf.models.apps_controller import HomeAppsController
from ldf.production import create_home_native
from tests.user_config import APPS_VERSION, HOME_SERVERS, TEST_DEVICES_GUIDS

APP_SERV_GUID = TEST_DEVICES_GUIDS['App Server']

pytestmark = pytest.mark.dependency


async def exec(client, coroutines: list):
    async with client:
        for coroutine in coroutines:
            await coroutine


async def disconnect_all_device_rx_sords(device):
    async with device:
        await device.addresses.disconnect(
            [sord for sord in device.sords(direction='rx')])


@pytest.fixture(scope='session')
def hac():
    """ HAC app manager object """
    return HomeAppsController(client_addrs=HOME_SERVERS)


@pytest.fixture(scope='session')
def target_app_server():
    """ Will create and return the App Server """

    return asyncio.run(
        create_home_native(
            lawo_type='App Server',
            guid=APP_SERV_GUID,
            client_addrs=HOME_SERVERS
        )
    )


@pytest.fixture(scope='function')
def device(built_test_device):
    # Device for test
    if not built_test_device.sords(direction='tx') and \
            not built_test_device.sords(direction='rx'):
        pytest.skip()
    yield built_test_device
    asyncio.run(disconnect_all_device_rx_sords(built_test_device))


@pytest.fixture(scope='class')
def set_up_app_devices(hac: HomeAppsController, target_app_server):
    app_base_configs: list[dict] = [
        {'label': 'QAA-SORD-TX-1', 'appType': 'tpg'},
        {'label': 'QAA-SORD-TX-2', 'appType': 'tpg'},
        {'label': 'QAA-SORD-RX-1', 'appType': 'mv', 'pips': 4},
        {'label': 'QAA-SORD-RX-2', 'appType': 'mv', 'pips': 4},
    ]
    for conf in app_base_configs:
        conf = hac.generate_app_config(conf['appType'], conf)
        asyncio.run(
            exec(
                hac,
                [
                    hac.create_app(conf['appType'], conf['label'], conf),
                    hac.start_app(target_app_server, conf['label'], APPS_VERSION)
                ]
            )
        )

    yield
    for conf in app_base_configs:
        asyncio.run(exec(hac, [hac.delete_app(conf['label'])]))


class TestConnectSords:

    async def test_one_to_many(self, set_up_app_devices, hac):

        async with hac:
            dev_1 = await hac.get_app_dev_by_name('QAA-SORD-TX-1')
            dev_2 = await hac.get_app_dev_by_name('QAA-SORD-RX-1')
            dev_3 = await hac.get_app_dev_by_name('QAA-SORD-RX-2')

        await connect_sords(
            {
                dev_1: [dev_1.sords(direction='tx')[0]]
            },
            {
                dev_2: [dev_2.sords(direction='rx')[2]],
                dev_3: dev_3.sords(direction='rx'),
            }
        )

    async def test_many_to_many(self, set_up_app_devices, hac):

        async with hac:
            dev_1 = await hac.get_app_dev_by_name('QAA-SORD-TX-1')
            dev_2 = await hac.get_app_dev_by_name('QAA-SORD-TX-2')
            dev_3 = await hac.get_app_dev_by_name('QAA-SORD-RX-1')
            dev_4 = await hac.get_app_dev_by_name('QAA-SORD-RX-2')

        # Connect sords 1:1 (TX sords and RX sords given must be equal)
        await connect_sords(
            # 6 x Total TX
            {
                dev_1: [dev_1.sords(direction='tx')[0]] * 3,
                dev_2: [dev_2.sords(direction='tx')[0]] * 3,
            },
            # 6 x Total RX
            {
                dev_3: [dev_3.sords(direction='rx')[-2],
                        dev_3.sords(direction='rx')[-1]],
                dev_4: dev_4.sords(direction='rx'),
            }
        )

    async def test_connect_device(self, device):
        await connect_sords(
            {device: [device.sords(direction='tx')[0]]},
            {device: [device.sords(direction='rx')[0]]}
        )

    async def test_disconnect_sords(self, device):
        await connect_sords(
            {device: [device.sords(direction='tx')[0]]},
            {device: [device.sords(direction='rx')[0]]}
        )
        await disconnect_destinations(
            {device: [device.sords(direction='rx')[0]]}
        )

    async def test_disconnect_flows(self, device):
        await connect_sords(
            {device: [device.sords(direction='tx')[0]]},
            {device: [device.sords(direction='rx')[0]]}
        )
        await disconnect_destinations(
            {device: [
                device.sords(direction='rx')[0].flows[0]]}
        )
