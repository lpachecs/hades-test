import logging

from datamodel.apps import apps_home
from datamodel.client.client import Client
from datamodel.ctls import ctls_home
from datamodel.endpoints import endpoints_home
from datamodel.kero.node import node_pb2
from nats.errors import NoRespondersError

from ldf.common.system.endpoints import allocate_guid
from ldf.models._manifest import model_manifest
from ldf.models.apps_controller import HomeAppsController
from ldf.models.base import (ClientConfig, HomeNativeDeviceSpec,
                             LawoHomeNativeDevice)
from ldf.models.edge import LawoDotEdgeDevice
from ldf.models.kero import LawoAppServer, LawoHomeNativeApp
from ldf.models.uhd_core import LawoUhdCoreDevice

log = logging.getLogger(__name__)


class UnknownDeviceError(Exception):
    """Exception raised when an unknown HOME device ID is supplied to the factory"""

    pass


class UnexpectedDeviceTypeError(Exception):
    """Exception raised when the device produced does not match the type requested"""

    pass


class GetEndpointError(Exception):
    """Exception raised when unable to get an endpoint for a device"""

    pass


async def _extend_edge_model(obj: LawoDotEdgeDevice) -> None:
    """Additional setup functions for .edge type devices

    Args:
        obj (LawoDotEdgeDevice): A partially populated .edge device model to extend
    """

    log.debug("!!! Device is .edge - Get SDI config")
    try:
        obj.sdi_config = [x.Selected for x in obj.endpoint.System.Profile.Options][0]
    except IndexError:
        obj.sdi_config = None
        log.warning("!!! Failed to obtain .edge IO configuration")
    obj.ctls, err = await ctls_home.ctls_get_ctl_all(obj.client, obj.id)


async def _extend_uhdcore_model(obj: LawoUhdCoreDevice) -> None:
    """Additional setup functions for UHD Core type devices
    Creates a virtual mixer model as class attributes for each mixer slice configured on core.

    Args:
        obj (LawoUhdCoreDevice): A partially populated UHD Core device model to extend
    """

    log.debug("!!! Device is UHD Core - Get child mixer configs")
    for mixer_id in obj.endpoint.System.ChildrenDeviceIDs:
        resp, err = await endpoints_home.endpoints_get_mixer_config(
            obj.client,
            mixer_id,
        )
        obj.mixers.configs[resp.Name] = resp

        # Creates class attributes for each mixer slice configured on core
        # TODO: Handle external NATs client when creating child vnmixers
        _, mixer_guid, _ = await endpoints_home.endpoints_get_guid(obj.client, mixer_id)
        setattr(
            obj.mixers,
            resp.Name,
            await create_home_native(
                lawo_type="Virtual Mixer",
                guid=mixer_guid,
                client_addrs=obj.client.addrs,
            ),
        )


async def _extend_app_model(obj: LawoHomeNativeApp) -> None:
    """Additional setup functions for App type devices

    Args:
        obj (LawoHomeNativeApp): An App device model to extend
    """
    # App info data
    app_info_msg = await apps_home.apps_get(
        obj.client, "", obj.guid, obj.label, "", "", 1, ""
    )
    try:
        obj.info = app_info_msg[0][0]
        obj.type = obj.info.Template.ID
    except IndexError as err:
        log.error(f"Failed to assign app info: {obj.label} {obj.id} {app_info_msg} {err}")
    finally:
        # Controls
        obj.ctls, _ = await ctls_home.ctls_get_ctl_all(obj.client, obj.id)


async def _extend_app_server_model(obj: LawoAppServer) -> None:
    """Additional setup functions for App Server type devices
    Gets additional attributes from datamodel/kero

    Args:
        obj (LawoAppServer): A partially populated App Server device model to extend
    """

    # App Server Node data
    requ = node_pb2.Get()
    resp = node_pb2.GetReply()
    await obj.client.request(f"kero.get.nodes.{obj.id}", requ, resp)
    obj.node = resp.Node
    # Controls
    obj.ctls, err = await ctls_home.ctls_get_ctl_all(obj.client, obj.id)


async def populate_model_object(obj: LawoHomeNativeDevice) -> LawoHomeNativeDevice:
    """Perform additional actions to populate models with real-world endpoint data

    Args:
        obj (LawoHomeNativeDevice): Unpopulated device model object to extend

    Raises:
        GetEndpointError: Raised if request to get.endpoint fails - assume device is offline

    Returns:
        LawoHomeNativeDevice: An LDF model that is populated with real-world endpoint data
    """

    try:
        obj.guid, obj.id = await allocate_guid(obj.client, obj.guid)
        obj.endpoint, _ = await endpoints_home.endpoints_get(obj.client, obj.id)
    except NoRespondersError as err:
        raise GetEndpointError(
            f"No Response from {obj.id} for get.endpoint, probably offline."
        ) from err
    finally:
        # Build the Addresses state machine for the endpoint
        await obj.addresses._sync_state()

    # Extend functionality for certain device types
    if isinstance(obj, LawoUhdCoreDevice):
        await _extend_uhdcore_model(obj)
    if isinstance(obj, LawoDotEdgeDevice):
        await _extend_edge_model(obj)
    if isinstance(obj, LawoAppServer):
        await _extend_app_server_model(obj)
    if isinstance(obj, LawoHomeNativeApp):
        await _extend_app_model(obj)

    # Copy current endpoint data into the model
    await obj.sync_endpoint()
    return obj


def prepare_model_object(lawo_type: str, nats_client: Client | None = None,
                         nats_servers: list[str] | None = None, nats_port: int = 4222,
                         api_key: str = "") -> LawoHomeNativeDevice:
    """Obtain the correct LDF model object for the requested device type

    If the requested device type is not matched in the model manifest, the default
    class object is returned - this will provide basic LDF functionality.

    If `nats_servers` is given, a standalone NATs client is created for the model
    If `nats_client` is given, the model will use the supplied NATs client

    Args:
        lawo_type (str): Requested device type
        nats_client (Client | None, optional): External NATs client to use with model. Defaults to None.
        nats_servers (list[str] | None, optional): Server IP addrs used when new NATs client created. Defaults to None.
        nats_port (int, optional): Port used when new NATs client created. Defaults to 4222.
        api_key (str, optional):  A HOME AAA api_key used for NATs communication authentication

    Returns:
        LawoHomeNativeDevice: An unpopulated model object of the requested device type.
    """
    try:
        target_device_object = model_manifest[lawo_type]
    except KeyError:
        log.warning(f"Requested type <{lawo_type}> not found in model manifest. Using default LawoHomeNativeDevice")
        target_device_object = LawoHomeNativeDevice
    finally:
        client_cfg = ClientConfig(client=nats_client, servers=nats_servers,
                                port=nats_port, api_key=api_key)

    return target_device_object(client_cfg)


async def create_home_native(lawo_type: str, guid: str, client_addrs: list[str] | None = None,
                             nats_port: int = 4222, nats_client: Client | None = None,
                             device_spec: HomeNativeDeviceSpec | None = None,
                             api_key: str = "") -> LawoHomeNativeDevice:
    """Produce a HOME native device object populated with live device data

    Args:
        type (str): Type of Lawo device type to be produced
        guid (str): GUID of the target device
        client_addrs (list[str]): List of IP addresses used by the target device for NATs comms
        nats_port (int): Port to use for communication with the NATs broker. Defaults to 4222.
        nats_client (Client): An external NATs client to assign as the `self.client` attribute for model
        api_key (str): A HOME AAA api_key used for NATs communication authentication
        device_spec (HomeNativeDeviceSpec | None): A description of the target device model details.

    Raises:
        UnknownDeviceError: Unknown device type string given
        UnexpectedDeviceTypeError: Requested device does not match the LawoDeviceType object

    Returns:
        LawoHomeNativeDevice: A LawoDevice object populated with current device data
    """

    obj = prepare_model_object(lawo_type, nats_servers=client_addrs,
                               nats_client=nats_client, nats_port=nats_port,
                               api_key=api_key)
    obj.guid = guid
    if not obj.spec:
        if not device_spec:
            log.debug(
                f"!!! {lawo_type} model does not have a device specification.\
                Some tests may be skipped."
            )
        else:
            obj.spec = device_spec

    async with obj.client:
        await populate_model_object(obj)
    log.info(f"Produced Model: {obj}")
    return obj


def create_home_apps_controller(client_addrs: list[str]) -> HomeAppsController:
    """Returns an instance of the HOME apps controller

    Used for:
        - Managing the lifecycle of HOME Apps
        - Maintaining high level information such as app updates
        - Any other high level HOME Apps realted operations in HOME
    """

    log.debug(f"Creating a HOME Apps controller for HOME system: {client_addrs}")
    return HomeAppsController(client_addrs)


async def listen_for_endpoint_call_home(home_addrs: list[str], num_collect=1):
    raise DeprecationWarning("listen_for_endpoint_call_home has moved to ldf/common/system/discovery.py.")
