import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, Coroutine, Iterable, Optional

from datamodel.addresses import addresses_pb2
from datamodel.client import client
from datamodel.endpoints import endpoints_home, endpoints_pb2
from ember_py import EmberClient
from google.protobuf.json_format import MessageToDict

from ldf.attributes.addresses import LawoHomeNativeAddresses
from ldf.attributes.controls import LawoHomeNativeControls
from ldf.attributes.inputs import LawoHomeNativeInputs
from ldf.attributes.interfaces import LawoHomeNativeInterfaces
from ldf.attributes.outputs import LawoHomeNativeOutputs
from ldf.attributes.sords import LawoHomeNativeSords
from ldf.attributes.terminals import LawoHomeNativeTerminals

ENDPOINT_SECTIONS = [
    "System",
    "UserInfo",
    "Interfaces",
    "Sords",
    "Terminals",
    "TerminalTags",
    "Connections",
    "Controls",
    "Params",
    "MixerConfig",
    "RedundancyGroup",
]


@dataclass
class ClientConfig:
    client: None | client.Client
    servers: None | list[str]
    port: int = 4222
    api_key: str = ""


@dataclass
class HomeNativeDeviceSpec:
    """A dataclass to provide device models with context"""

    type_number: str
    model: str
    flags: dict[str, bool]
    terminals: Optional[dict] = None


class HeartbeatTimeoutError(Exception):
    """Exception raised when we do not receive a device heartbeat within the specified timeout period"""
    pass


class LawoHomeNativeDevice:

    def __init__(
        self,
        client_cfg: ClientConfig,
        ember_client: EmberClient | None = None,
        spec: HomeNativeDeviceSpec | None = None,
    ) -> None:

        self.log = logging.getLogger(__name__)
        if client_cfg.client:
            self.client = client_cfg.client
        elif not client_cfg.client and client_cfg.servers:
            self.client = client.Client(client_cfg.servers, port=client_cfg.port,
                                        api_key=client_cfg.api_key)
        else:
            raise TypeError("Falied to configure NATs client w/ ClientConfig object")

        self.endpoint = endpoints_pb2.Endpoint()
        self.id: str = ""
        self.guid: str = ""
        self.spec = spec
        self.addresses = LawoHomeNativeAddresses(self)
        self.interfaces = LawoHomeNativeInterfaces(self)
        self.controls = LawoHomeNativeControls(self)
        self.sords = LawoHomeNativeSords(self)
        self.terminals = LawoHomeNativeTerminals(self)
        self.inputs = LawoHomeNativeInputs(self)
        self.outputs = LawoHomeNativeOutputs(self)
        self.ember = ember_client

    def __repr__(self):
        return f"<{type(self).__name__} {self.id} {self.label}>"

    async def __aenter__(self) -> None:
        """An asynchronous context manager for handling device connections and subscriptions"""

        e = asyncio.Event()
        await self.client.connect()
        # Copy current endpoint data into the model
        await self.sync_endpoint()
        await self.addresses._sync_state()
        await subscribe_for_updates(self.client, self._updates(), event=e)
        await e.wait()

    async def __aexit__(self, *args):
        await self.client.disconnect()

    @property
    def label(self) -> str:
        return self.endpoint.UserInfo.Label

    @property
    def location(self) -> str:
        return self.endpoint.UserInfo.Location

    @property
    def model(self) -> str:
        return self.endpoint.System.Model

    @property
    def type_num(self) -> str:
        return self.endpoint.System.TypeNumber

    @property
    def sw_version(self) -> str:
        return self.endpoint.System.SwVersion

    @property
    def hw_version(self) -> str:
        return self.endpoint.System.HwVersion

    @property
    def profile(self) -> str:
        return self.endpoint.System.Profile

    @property
    def flags(self) -> dict[str, bool]:
        return MessageToDict(self.endpoint.System.Flags)

    @property
    def application(self) -> endpoints_pb2.Option:
        return self.endpoint.System.Profile.Application

    @application.setter
    def application(self, other: endpoints_pb2.Option):
        self.endpoint.System.Profile.Application = other

    @property
    def options(self) -> Iterable[endpoints_pb2.Option]:
        return self.endpoint.System.Profile.Options

    @options.setter
    def options(self, other: list[endpoints_pb2.Option]):
        self.endpoint.System.Profile.Application.MergeFrom(other)

    def _updates(self) -> list[tuple[str, Callable]]:
        """Define the updates to register for on connection along with handler callback

        Returns:
            list[tuple[str, Coroutine]]: Subscription subjects and handler callbacks
        """

        return [
            (f"update.endpoints.{self.id}.>", self.cb_update_endpoint),
            ("update.addresses.>", self.cb_update_addresses),
        ]

    async def cb_update_endpoint(self, msg):
        """Apply an incoming Endpoint update to the device model

        Args:
            msg (_type_): Incomming message from subscription channel
        """

        # Determine the type of operation to be performed (insert, change, remove) and
        # which section of the endpoint is being modified.
        update_op = msg.subject.split(".")[-1]
        if update_op == "reset":
            await self.sync_endpoint()
            return
        else:
            modified_key = msg.subject.split(".")[-2]
            modified_section = {
                "userinfo": "UserInfo",
                "mixerconfig": "MixerConfig",
                "redundancygroup": "RedundancyGroup",
                "networks": "Interfaces",
            }.get(
                modified_key,
                modified_key.title()
            )

        update_data = endpoints_pb2.Endpoint()
        update_data.MergeFromString(msg.data)
        try:
            headers = msg.headers
            self.log.debug(f"[UPDATE Endpoint]: {headers}")
        except AttributeError:
            self.log.debug("[UPDATE Endpoint]: No Headers found in update!")
        self.log.debug(
            f"[UPDATE Endpoint]: {self.label} >> {msg.subject} >> {update_data}"
        )

        # Get repeated containers containing old and updated data
        local_endpoint_section = getattr(self.endpoint, modified_section)
        updated_section = getattr(update_data, modified_section)

        try:
            stale_data = [
                x for x in local_endpoint_section
                if x.ID in [y.ID for y in updated_section]
            ]

        # Endpoint "Connections" use SrcID / DstID
        except AttributeError:
            stale_data = [
                x for x in local_endpoint_section
                if x.DstID in [y.DstID for y in updated_section]
            ]

        # If non-iterable section of endpoint eg. UserInfo
        except TypeError:
            stale_data = []

        # Perform the update operation on the data
        match update_op:
            case "insert":
                self.endpoint.MergeFromString(msg.data)
            case "remove":
                for x in stale_data:
                    local_endpoint_section.remove(x)
            case "change":
                self.endpoint.MergeFromString(msg.data)
                for x in stale_data:
                    local_endpoint_section.remove(x)

    async def cb_update_addresses(self, msg):
        """Handles incoming address updates for this device only

        Args:
            msg (_type_): _description_
        """

        update_op = msg.subject.split(".")[-1]
        update = addresses_pb2.Update()
        update.MergeFromString(msg.data)
        for address in update.Addresses:
            gate = address.Gate
            if self.id != gate.DevID:
                continue
            if update_op in ["insert", "change"]:
                self.addresses.state[address.ID] = address
            elif update_op == "remove":
                try:
                    del self.addresses.state[address.ID]
                except KeyError:
                    self.log.debug(
                        f"!!! Ignoring duplicate remove update for: {address.ID}"
                    )
            self.log.debug(
                f"[UPDATE Addresses]: {self.label} >> {update_op} >> {address.ID}"
            )

    async def wait_for_heartbeats(
        self, num_of_hbs: int = 3, timeout: int | None = None
    ):
        """Blocking function that will halt code until x number of heartbeat messages are
        received from the target device

        Args:
            num_of_hbs (int, optional): The number of heartbeat messages to wait for. Defaults to 3.
            timeout (int | None, optional): A maximum value to wait before failing (seconds). Defaults to None.

        Raises:
            HeartbeatTimeoutError: Raised if a supplied timeout value is exceeded
        """

        hbs = []
        tn = time.perf_counter()
        sub = f"heartbeat.endpoints.{self.id}"

        async def cb_heartbeat(msg):
            _, _, device_id = msg.subject.split(".")
            if device_id == self.id:
                self.log.info(f"Heatbeat received for {device_id}")
                hbs.append(msg)

        self.log.info(f"Waiting for heartbeats from {self.label} on {sub}")
        await self.client.sub(sub, cb_heartbeat)

        while len(hbs) < num_of_hbs:
            if not timeout:
                await asyncio.sleep(1)
            else:
                delta = time.perf_counter() - tn
                if delta >= timeout:
                    self.log.error(
                        f"Exceeded timeout of {timeout}s when waiting for device heartbeats"
                    )
                    raise HeartbeatTimeoutError(
                        "Failed to receive heartbeat from the device within timeout"
                    )

    async def sync_endpoint(self):
        """Called to manually sync the model endpoint data with real world"""

        self.endpoint, _ = await endpoints_home.endpoints_get(self.client, self.id)

    def copy_endpoint(
        self,
        isolate_sections: list = ENDPOINT_SECTIONS
    ) -> endpoints_pb2.Endpoint:
        """Create a copy of the device endpoint data with optional sections preserved"

        Args:
            isolate_sections (list, optional): Sections of the endpoint to keep in the copy. Defaults to all.

        Returns:
            endpoints_pb2.Endpoint: A copy of the device endpoint with specified sections preserved
        """

        e = endpoints_pb2.Endpoint()
        e.ID = self.id
        e.GUID = self.guid
        for section in isolate_sections:
            try:
                s = getattr(e, section)
            except AttributeError:
                self.log.warning(f"{self.label} is not have a {section} section")
                continue
            s.MergeFrom(getattr(self.endpoint, section))

        return e

    async def reboot(self) -> None:
        """Send a NATs request to reboot the target device"""
        return await endpoints_home.endpoints_reboot(self.client, self.id)

    async def get_sections(self, sections: list[str]) -> endpoints_pb2.Endpoint:
        """Requests individual sections of the device endpoint

        Returns:
            endpoints_pb2.Endpoint: Endpoint containing the requested sections.
        """

        flags = endpoints_pb2.Sections()
        for section in sections:
            try:
                setattr(flags, section, True)
            except AttributeError:
                self.log.error(f"Unkown get.sections flag: {section}")

        data, _ = await endpoints_home.endpoints_get_sections(
            self.client, self.id, flags
        )
        return data


async def subscribe_for_updates(
    client: client.Client,
    subs: list[tuple[str, Callable]],
    event: asyncio.Event | None = None,
) -> list[asyncio.Task[Coroutine]]:
    """Subscribe to multiple NATs subjects for updates using apropriate callback functions

    Args:
        client (client.Client): datamodel.client object used to connect to NATs broker
        subs (list[tuple[str, Coroutine]]): Address + Handler pairings for device model updates

    Returns:
        list[Coroutine]: References to subscription tasks
    """

    subscriptions = [asyncio.create_task(client.sub(sub, cb)) for sub, cb in subs]

    for task in subscriptions:
        await task
    if event:
        event.set()
    return subscriptions
