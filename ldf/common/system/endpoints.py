from dataclasses import dataclass

from datamodel.client.client import Client
from datamodel.devices import devices_home
from datamodel.devices.devices_pb2 import AliveState, DeviceStatus
from datamodel.endpoints import endpoints_home, endpoints_pb2
from datamodel.endpoints.endpoints_pb2 import Endpoint
from datamodel.registrations import registrations_home
from datamodel.registrations.registrations_pb2 import (Credentials, DeviceType,
                                                       Entry)
from google.protobuf.json_format import MessageToDict
from nats.errors import NoRespondersError, TimeoutError


@dataclass
class HomeDeviceListEntry:
    home_id: str
    label: str
    model: str
    guid: str
    state: str
    flags: dict

    def __str__(self) -> str:
        return " | ".join([self.guid, self.home_id, self.model, self.label, self.state])


def create_home_device_list_entry(dev: DeviceStatus) -> HomeDeviceListEntry:
    """Create a HomeDeviceListEntry object from a DeviceStatus protobuf message.

    Args:
        dev (devices_pb2.DeviceStatus): The DeviceStatus protobuf message.

    Returns:
        HomeDeviceListEntry: The created HomeDeviceListEntry object.
    """

    entry = HomeDeviceListEntry(
        home_id=dev.ID,
        label=dev.Label,
        model=dev.Model,
        guid=dev.GUID,
        state=AliveState.Name(dev.Alive).lower(),
        flags=MessageToDict(dev.Flags)
    )

    return entry


async def allocate_guid(nats_client: Client, device_guid: str) -> tuple[str, str]:
    """Request a device ID from discovery service using the device GUID

    Args:
        client (Client): The NATS client instance.
        guid (str): GUID of the target to allocate

    Returns:
        tuple[str, str]: The GUID and ID returned from discovery service
    """

    guid, dev_id, err = await devices_home.devices_allocate(nats_client, device_guid)
    if err:
        raise Exception(f"!!! Error allocating device ID: {err}")
    return guid, dev_id


async def collect_and_sort_endpoints(nats_client: Client) -> dict[str, dict[str, HomeDeviceListEntry]]:
    """Generate a dictionary of all endpoints discovered in a HOME devices
    list and sort by type

    Returns:
        dict[str, dict[str, HomeDeviceListEntry]]: A dictionary containing sorted endpoints=
    """

    async def collect_endpoints():
        devices, err = await devices_home.devices_get_all(nats_client)
        if err:
            raise Exception(f"Failed to get devices list: {err}")
        else:
            return devices

    app = {}
    switch = {}
    device = {}
    for dev in await collect_endpoints():
        endpoint = create_home_device_list_entry(dev)
        if endpoint.flags.get('IsNetworkSwitch', None):
            switch[dev.ID] = endpoint
        elif endpoint.flags.get('IsHomeApp', None):
            app[dev.ID] = endpoint
        else:
            device[dev.ID] = endpoint

    return {
        "switch": switch,
        "app": app,
        "device": device
    }


async def get_endpoint_sections(client: Client, device_id: str) -> Endpoint | None:
    """Return a Endpoint object with requested sections included in the reply.

    Args:
        client (Client): A NATs client object configured against valid HOME servers
        device_id (str): A string representation of the device ID to query

    Returns:
        endpoints_pb2.Endpoint | None: The Endpoint object with requested sections or None if not found
    """

    section = endpoints_pb2.Sections()
    section.Sords = True
    section.Interfaces = True
    try:
        endpoint, _ = await endpoints_home.endpoints_get_sections(
            client, device_id, section
        )
        return endpoint
    except (NoRespondersError, TimeoutError):
        return None


async def get_home_proxy_list(nats_client, ids=""):
    """Return a list of all device proxies configured on the system"""

    proxies, err = await registrations_home.registrations_get(
        nats_client,
        argID=ids
    )
    return [x for x in proxies]


async def create_home_proxy_device(
        nats_client: Client,
        label: str,
        proxy_type: str,
        ip_address: str,
        port: int
) -> Entry:
    """Create a home proxy device.

    Args:
        nats_client (Client): The NATS client instance.
        label (str): The label for the proxy device.
        proxy_type (str): The type of the proxy device.
        ip_address (str): The IP address of the proxy device.
        port (int): The port of the proxy device.

    Raises:
        RuntimeError: If the proxy device creation fails.
        RuntimeError: If the proxy device retrieval fails.

    Returns:
        registrations_pb2.Entry: The reg data for the created proxy device.

    Example:
        proxy = await create_home_proxy_device(
            nats_client,
            label="Test Proxy Device",
            proxy_type="third_party",
            ip_address="192.168.1.100",
            port=8080
    """

    async with nats_client:
        proxy_reg, err = await registrations_home.registrations_create(
            nats_client,
            argLabel=label,
            argType=DeviceType.Value(proxy_type.upper()),
            argIP=ip_address,
            argPort=port,
            argLocation="",
            argBackupIP="",
            argBackupPort=0,
            argCredentials=Credentials(Username="", Password="")
        )
        if err:
            raise RuntimeError(f"Failed to create proxy device: {err}")
        else:
            return proxy_reg


async def remove_home_proxy_device(nats_client: Client, device_ids: list[str]) -> list[str]:
    """Remove a home proxy device.

    Args:
        nats_client (Client): The NATS client instance.
        device_ids (list[str]): The IDs of the proxy devices to remove.

    Raises:
        RuntimeError: If the proxy device removal fails.
    """

    async with nats_client:
        removed, err = await registrations_home.registrations_delete(
            nats_client,
            device_ids
        )
        if err:
            raise RuntimeError(f"Failed to delete proxy device: {err}")
        else:
            return [x for x in removed]
