import asyncio
import itertools
import random
import re

import pytest
from datamodel.apps import apps_pb2
from datamodel.devices import devices_home
from datamodel.sords.sords_pb2 import Encap
from nats.errors import TimeoutError as NATSTimeoutError

from ldf.common.connections import connect_sords
from ldf.models.apps_controller import HomeAppsController
from ldf.models.kero import LawoAppServer
from ldf.production import create_home_native
from tests import log
from tests.user_config import (APPS_VERSION, HOME_SERVERS, TEST_DEVICES_GUIDS,
                               VIRTUAL_SERVERS)

pytestmark = pytest.mark.dependency


APP_SERVER_GUID = TEST_DEVICES_GUIDS['App Server']


""" Helper Functions """


async def exec_coroutine(client, coroutine):
    async with client:
        return await coroutine


""" Device fixtures """


@pytest.fixture(scope='session')
def target_app_server() -> LawoAppServer:
    """ Will create and return the App Server """

    return asyncio.run(
        create_home_native(
            lawo_type='App Server',
            guid=APP_SERVER_GUID,
            client_addrs=HOME_SERVERS
        )
    )


@pytest.fixture(scope='session')
def hac():
    """ HAC app manager object """
    hac = HomeAppsController(
        client_addrs=HOME_SERVERS,
        tracked_names=['QAA.*']
    )
    return hac


""" Setup fixtures """


@pytest.fixture(
    scope='session',
    params=[
        # 2110 input and 2110 output UDX
        ('QAA-LDF-UDX-JXS', 'udx', {'inputVideoTransport': '2110-22', 'colluts': True}),
        # NDI input and NDI output MV
        ('QAA-LDF-MV-NDI', 'mv', {'inputVideoTransport': 'ndi', 'pips': 2})
    ],
    ids=lambda param: param[0]
)
def app_configs(request, hac: HomeAppsController) -> list[str, str, dict]:
    """ Will return a dictionary describing each home app configuration for tests

    Returns:
        dict: a dictionary where:
            - the key is the id of a HOME app setting
            - the value is the value of the setting
            - this matches the JSON dictionary string expected from HOME to create an app
    """
    app_name, app_type, config = request.param
    return (app_name, app_type, hac.generate_app_config(app_type, config))


""" System cleanup fixtures """


@pytest.fixture(scope='session', autouse=True)
def clean_up_apps(hac):
    """ Will delete any HOME Apps with 'LDF' in the name after test run """
    yield
    ldf_app_names = [app_data.label for app_data in hac.data if 'ldf' in app_data.label.lower()]
    try:
        if ldf_app_names:
            asyncio.run(
                exec_coroutine(
                    hac, hac.delete_apps([ldf_app_names], blocking=False)))
    except Exception as e:
        log.debug(str(e))


""" Single app lifecycle test / HAC.data test """


async def test_hac_lifecycle(hac, app_configs, target_app_server):
    """ Will test HAC lifecycle functions and the that hac.data dictionary contains
        expected information based on the HOME apps actions performed on the system
    """

    app_name, app_type, app_config = app_configs

    async with hac:
        # Nothing should be in hac.data before adding the app to the system
        assert hac.data == {}
        # App Create
        await hac.create_app(app_name, app_type, app_config)
        # Once created HAC contains App data
        app_data = hac.data[app_name]
        # Ensure the app under test has been added to App data
        assert app_name in hac.data
        # App Start
        await hac.start_app(app_name, target_app_server, APPS_VERSION)
        assert app_data.state == 'running'
        # App Stop
        await hac.stop_app(app_name)
        assert app_data.state == 'stopped'
        # App Delete
        await hac.delete_app(app_name)
        assert app_name not in hac.data


async def test_hac_gang_lifecycle(hac, target_app_server):
    """ Repeats the above test but for multiple apps """

    # Create a set of TPGs with differing output transport types
    app_configurations = {
        'QAA-LDF-TPG-2110': ('tpg', {'outputVideoTransport': '2110'}),
        'QAA-LDF-TPG-JPEG': ('tpg', {'outputVideoTransport': '2110-22'}),
        'QAA-LDF-TPG-NDIo': ('tpg', {'outputVideoTransport': 'ndi'}),
        'QAA-LDF-TPG-SRTo': ('tpg', {'outputVideoTransport': 'srt-264'}),
    }

    app_names = app_configurations.keys()

    async with hac:
        assert hac.data == {}
        # Apps Create, Assert all are in HAC.data
        await hac.create_apps(app_configurations)
        assert set(app_names).issubset(hac.data.keys())
        # Apps Start, Assert all apps are running
        await hac.start_apps(app_names, target_app_server, APPS_VERSION)
        assert all(app_data.state == 'running' for app_data in hac.data.values())
        # Apps Stop, Assert all apps are stopped
        await hac.stop_apps(app_names)
        assert all(app_data.state == 'stopped' for app_data in hac.data.values())
        # Apps Delete, Assert all apps are deleted from system
        await hac.delete_apps(app_names)
        assert hac.data == {}


""" Other tests """


@pytest.fixture(scope='function')
def create_app(hac, app_configs):
    """ Will create the app under test if not already on the system """

    app_name, app_type, app_config = app_configs
    asyncio.run(exec_coroutine(hac, hac.create_app(app_name, app_type, app_config)))
    yield
    asyncio.run(exec_coroutine(hac, hac.delete_app(app_name)))


@pytest.fixture(scope='function')
def start_app(hac, create_app, app_configs, target_app_server):
    """ Will create and start the App under test in HOME, Then delete the app on cleanup """

    app_name, _, _ = app_configs
    asyncio.run(exec_coroutine(hac, hac.start_app(app_name, target_app_server, APPS_VERSION)))
    return asyncio.run(exec_coroutine(hac, hac.get_app_dev_by_name(app_name)))


async def test_create_tpg_for_destination(start_app, hac, app_configs, target_app_server):

    """ Will test creation of a TPG with HAC

        To create the TPG HAC only needs to be provided a destination sord
        Based on the desination sord attributes a suitable TPG will be created so it can be used as a source
        After the TPG is created its sender can be connected to the App under test receiver
    """

    _, _, app_config = app_configs

    async with hac:

        # Get the first receiver sord from the app under test
        target_app = start_app
        dst_sord = target_app.sords(direction='rx')[0]

        # Create the TPG app based on the sord - We can define some custom TPG configs in a dictionary
        # Here we want:
        # - The test pattern to be a Zone Plate
        # - The output scan rate to match the receiving home app, or random if it doesn't matter
        #     - (For an MV the source scan rate must match, for a UDX it doesn't matter if it's set to 'follow')
        tpg_config = {
            'pattern': 'zoneplate',
            'outputScanRate': app_config['outputScanRate'] if not app_config['outputScanRate'] == 'follow'
            else random.choice(['50', '59', '60'])
        }

        # Create the TPG with for the given receiver sord
        tpg_dev = await hac.create_tpg_for_destination_sord(
            'QAA-LDF-TPG',
            target_app_server,
            APPS_VERSION,
            dst_sord,
            custom=tpg_config,
        )

        # Assert the Source TPG sord is suitable for the Destination sord of the App Under test
        src_sord = tpg_dev.sords(direction='tx')[0]
        # The video streams should be compatible for connection
        assert src_sord.flows[0].caps[0] in dst_sord.flows[0].caps
        assert src_sord.flows[0].essence == dst_sord.flows[0].essence
        # The audio streams should be compatible for connection
        if app_config['inputAudioTransport'] == '2110':
            assert src_sord.flows[1].caps[0] in dst_sord.flows[1].caps
            assert src_sord.flows[1].essence == dst_sord.flows[1].essence

        # We can connect the TPG to the target device receivers
        await connect_sords(
            {tpg_dev: tpg_dev.sords()}, {target_app: target_app.sords(direction='rx')})

        # We can delete the TPG from HOME
        await hac.delete_app(tpg_dev.label)


async def test_create_stc_for_source(start_app, hac, app_configs, target_app_server):

    """ Will test creation of a STC with HAC

        To create the STC HAC only needs to be provided a source sord
        Based on the desination sord attributes a suitable STC which the app can patch to
        The test will connect the sender to the STC
    """

    _, _, app_config = app_configs

    async with hac:

        # Get the first receiver sord from the app under test
        target_app = start_app
        src_sord = target_app.sords(direction='tx')[0]

        # Create the TPG with for the given receiver sord
        stc_dev = await hac.create_stc_for_source_sord(
            'QAA-LDF-STC',
            target_app_server,
            APPS_VERSION,
            src_sord
        )

        # Assert the Destination STC sord is suitable for the Source sord of the App Under test
        dst_sord = stc_dev.sords(direction='rx')[0]
        # The video streams should be compatible for connection
        assert src_sord.flows[0].caps[0] in dst_sord.flows[0].caps
        assert src_sord.flows[0].essence == dst_sord.flows[0].essence
        # The audio streams should be compatible for connection
        if app_config['inputAudioTransport'] == '2110':
            assert src_sord.flows[1].caps[0] in dst_sord.flows[1].caps
            assert src_sord.flows[1].essence == dst_sord.flows[1].essence

        # We can connect the test app to the STC
        await connect_sords(
            {target_app: [src_sord]}, {stc_dev: [dst_sord]})

        # We can delete the TPG from HOME
        await hac.delete_app(stc_dev.label)


async def test_get_app_device(hac, start_app, app_configs):
    """ Gets an App LDF device from HAC """

    app_name, _, _ = app_configs
    async with hac:
        device = await hac.get_app_dev_by_name(app_name)
    assert device.info.State == 'running'


""" App Server Node (Only run these tests on empty servers) """


async def test_app_server_node(hac, start_app, app_configs, target_app_server):
    """ An app server has a Node attribute from the datamodel/kero
    This contains useful information such as the current io allocation on a sever
    """

    app_name, _, app_config = app_configs
    async with hac:
        app_dev = await hac.get_app_dev_by_name(app_name)
    costs = hac.info['server']['input_costs']
    async with target_app_server:
        recv_consumption = target_app_server.node.Io.ReceiverNominalConsumption
        send_consumption = target_app_server.node.Io.SenderNominalConsumption
    recv_sords = len(app_dev.sords(direction='rx'))
    send_sords = len(app_dev.sords(direction='tx'))

    assert (costs.get(app_config['inputResolution']) * recv_sords) \
        if app_dev.sords(direction='rx')[0].flows[0].encap != Encap.NDI else 0 \
        == recv_consumption
    assert (costs.get(app_config['outputResolution']) * send_sords) \
        == send_consumption


""" Scalability tests (gang lifecycle operations) WARNING - could break a HOME system """


async def create_all_apps(hac: HomeAppsController, all_configs: dict[str: dict]):
    async with hac:
        await hac.create_apps(
            all_configs,
            timeout='auto'
        )


async def delete_all_apps(hac: HomeAppsController, app_names: list[str]):
    async with hac:
        await hac.delete_apps(app_names)


@pytest.fixture(scope='session')
def virtual_app_servers(hac) -> list[LawoAppServer]:
    """ Will get a list of virtual app server LDF devices

    For this test to run user config should have this dictionary:

    VIRTUAL_SERVERS = {
        "names": "QAA-VIRTUAL-SERVER-%d",
        "range": range(1, 17),
    }
    """

    if not VIRTUAL_SERVERS.get('names') or not VIRTUAL_SERVERS.get('range'):
        pytest.skip()

    server_devices = []

    server_names = [
        f"{VIRTUAL_SERVERS['names'].replace('%d', str(num))}" for num in VIRTUAL_SERVERS['range']]

    all_devices, _ = asyncio.run(exec_coroutine(
        hac.client, devices_home.devices_get_all(hac.client)
    ))

    server_device_protos = [d for d in all_devices if d.Label in server_names]

    for proto in server_device_protos:
        server_devices.append(
            asyncio.run(exec_coroutine(hac.client, create_home_native(
                lawo_type='App Server',
                guid=proto.GUID,
                client_addrs=HOME_SERVERS
            )))
        )

    return server_devices


@pytest.fixture(scope='function')
def create_virtual_apps(hac, virtual_app_servers):
    """ Will create 16 x MVs for each given virtual app server under test

    Returns:
        A dictionary mapping the servers and their expected apps

    E.G.:
        {
            server 1: [app-1-1, app-1-2, app-1-3, ...],
            server 2: [app-2-1, app-2-2, app-2-3, ...],
            ...
        }
    """

    # Create configs for every app

    all_configs = {}

    servers_and_apps_grouped = {}

    base_mv_confs = {'appType': 'mv', 'pips': 16, 'inputResolution': 'dynamic', 'outputAudioChannels': '16'}

    for server in virtual_app_servers:
        servers_and_apps_grouped[server.guid] = []
        for i in range(1, 16 + 1):
            # Create the configs for the apps
            app_name = f"QAA-VAPP-SERV-{server.label.split('-')[-1]}-APP-{i}"
            app_type = 'mv'
            conf = base_mv_confs.copy()
            conf = hac.generate_app_config(app_type=app_type, custom=conf)
            all_configs.update({app_name: (app_type, conf)})
            # Group servers and app names in a simple dictionary
            servers_and_apps_grouped[server.guid].append(app_name)

    asyncio.run(create_all_apps(hac, all_configs))

    yield servers_and_apps_grouped

    asyncio.run(delete_all_apps(hac, list(all_configs.keys())))


class TestScalabilityFunctions:

    """ !!!NOTE!!!: For this test to run user config should have this dictionary:

    VIRTUAL_SERVERS = {
        "names": "QAA-VIRTUAL-SERVER-%d",
        "range": range(1, 17),
    }
    """

    async def test_gang_start_blocking(self, virtual_app_servers, create_virtual_apps, hac: HomeAppsController):
        """ We will puposely raise an error by setting timeouts to be too low """

        # In this test we will group up all the apps by their given server target

        servers_and_apps_grouped = create_virtual_apps

        # Next we will gang start all apps, server by server

        try:
            async with hac:
                for server_guid, list_of_apps_to_start_on_server in servers_and_apps_grouped.items():
                    await hac.start_apps(
                        app_names=list_of_apps_to_start_on_server,
                        target_app_server=server_guid,
                        version=APPS_VERSION,
                        timeout_start=0.0001,
                        timeout_health=0.0001,
                        blocking=True,
                    )
        except TimeoutError:
            log.info("Test passed - the correct Timeout error was raised")
            assert True
        except Exception as e:
            assert False, f"Test failed, the Timeout error was not raised: {e}"
        else:
            assert False, "Expected TimeoutError was not raised"

    async def test_gang_start_non_blocking(self, virtual_app_servers, create_virtual_apps, hac: HomeAppsController):
        """ Non blocking - We will set the timeouts low so that app's arent started or healthy in expected times,
            but will only raise an error not a warning

            The result should now be given
        """

        # In this test we will group up all the apps by their given server target

        servers_and_apps_grouped = create_virtual_apps

        # Next we will gang start all apps, server by server

        async with hac:
            for server_guid, list_of_apps_to_start_on_server in servers_and_apps_grouped.items():
                result = await hac.start_apps(
                    app_names=list_of_apps_to_start_on_server,
                    target_app_server=server_guid,
                    version=APPS_VERSION,
                    timeout_start='auto',
                    timeout_health=None,
                    blocking=False,
                )

        # All apps will start, but they should all be unhealthy

        result_started, result_healthy = result

        assert all(res is True for res in result_started.values())
        assert all(res is False for res in result_healthy.values())

    async def test_gang_stop(self, virtual_app_servers, create_virtual_apps, hac):

        # In this test we will get a list of every single app on every server
        # E.G. [app-on-serv-1-1, app-on-serv-1-2, app-on-serv-2-1, app-on-serv-2-2, ...]

        names_of_every_app_on_system = list(itertools.chain.from_iterable(create_virtual_apps.values()))

        # Next we will gang stop all apps

        async with hac:
            result = await hac.stop_apps(
                app_names=names_of_every_app_on_system,
                timeout='auto',
            )

        # The result should show all apps have stopped

        assert all(res is True for res in result.values())

    async def test_gang_delete(self, virtual_app_servers, create_virtual_apps, hac):

        names_of_every_app_on_system = list(itertools.chain.from_iterable(create_virtual_apps.values()))

        # Next we will gang stop all apps

        async with hac:
            result = await hac.delete_apps(
                app_names=names_of_every_app_on_system,
                timeout=None,
            )

        # The result should show all apps have been delted

        assert all(res is True for res in result.values())

    async def test_gang_edit(self, virtual_app_servers, create_virtual_apps, hac):

        names_of_every_app_on_system = list(itertools.chain.from_iterable(create_virtual_apps.values()))
        app_names = [
            name for name in names_of_every_app_on_system if bool(re.search(r'\d-APP-2\Z', name))]

        # edit the second app on each server - set all output audio streams to 8

        configs = {app_name: hac.data[app_name].configuration for app_name in app_names}

        for config in configs.values():
            config['outputAudioChannels'] = 8

        # We raise an error because one of the apps won't update

        configs[app_names[0]].update({'outputResolution': 'Heheheha'})

        try:
            async with hac:
                await hac.edit_apps(configs)
        except NATSTimeoutError:
            assert True

    async def test_gang_edit_non_blocking(self, virtual_app_servers, create_virtual_apps, hac):

        names_of_every_app_on_system = list(itertools.chain.from_iterable(create_virtual_apps.values()))
        app_names = [
            name for name in names_of_every_app_on_system if bool(re.search(r'\d-APP-2\Z', name))]

        # edit the second app on each server - set all output audio streams to 8

        configs = {app_name: hac.data[app_name].configuration for app_name in app_names}

        for config in configs.values():
            config['outputAudioChannels'] = 8

        # We will raise an error because one of the apps won't update

        configs[app_names[0]].update({'outputResolution': 'Heheheha'})

        async with hac:
            result = await hac.edit_apps(configs, blocking=False)

        assert list(result.values()) == [False] + [True] * (len(configs) - 1)


@pytest.fixture(scope='function')
def create_licensed_and_unlicensed_apps(hac):
    """ Will create one licensable app and one unlicensable apps """
    apps_to_create = {
        'QAA-LDF-LIC': None,
        'QAA-LDF-UNLIC': None,
    }
    for (app_name, transport) in zip(apps_to_create.keys(), ('2110', '2110-22')):
        config = hac.generate_app_config('udx', {'outputVideoTransport': transport})
        apps_to_create[app_name] = ('udx', config)
    asyncio.run(exec_coroutine(hac, hac.create_apps(apps_to_create)))
    yield apps_to_create
    asyncio.run(exec_coroutine(hac, hac.delete_apps(apps_to_create.keys())))


@pytest.fixture(scope='function')
def set_license_mode_credits(hac, create_licensed_and_unlicensed_apps):
    """ Will set the licesning mode of the apps to credits """

    configs = {app_name: values[1] for app_name, values in create_licensed_and_unlicensed_apps.items()}
    asyncio.run(exec_coroutine(hac, hac.edit_apps(configs, license_mode=apps_pb2.LicenseMode.FLEX)))


class TestAppLicensingCheck:

    # An app with a JXS sender and credits enabled is used to test this
    # because a JXS sender can only be perpetual

    async def test_starting_unlicensed_app_raises_error(
            self, hac, create_licensed_and_unlicensed_apps, target_app_server, set_license_mode_credits):
        try:
            async with hac:
                await hac.start_apps(
                    app_names=create_licensed_and_unlicensed_apps.keys(),
                    target_app_server=target_app_server,
                    version=APPS_VERSION,
                    blocking=True,
                )
        except AssertionError as e:
            log.info(f"Error raised: {str(e)}")
            assert "HAC raised an assertion error because one of the apps could not start due to invalid licenses"

    async def test_starting_unlicensed_app_raises_warning(
            self, hac, create_licensed_and_unlicensed_apps, target_app_server, set_license_mode_credits):
        async with hac:
            licensed_app_data, unlicensed_app_data = await hac.start_apps(
                app_names=create_licensed_and_unlicensed_apps.keys(),
                target_app_server=target_app_server,
                version=APPS_VERSION,
                blocking=False,
            )
        result = [app_data.state == 'running' for app_data in (licensed_app_data, unlicensed_app_data)]
        assert result == [True, False]
