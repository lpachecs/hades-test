import asyncio
import logging
from typing import Any, Iterator

from datamodel.client.client import Client
from datamodel.devices import devices_home
from datamodel.devices.devices_pb2 import DeviceStatus
from datamodel.registrations.registrations_pb2 import Entry

from ldf.common.system.endpoints import (HomeDeviceListEntry,
                                         create_home_device_list_entry,
                                         create_home_proxy_device,
                                         remove_home_proxy_device)
from ldf.models.base import LawoHomeNativeDevice
from ldf.production import (GetEndpointError, UnknownDeviceError,
                            populate_model_object, prepare_model_object)


class DeviceNotFoundError(Exception):
    """Exception raised when a device is not found in the HOME devices list."""
    pass


class HomeControllerEndpoints:

    def __init__(
        self,
        nats_client: Client,
        endpoints: dict[str, dict[str, HomeDeviceListEntry]],
        proxies: list[Entry]
    ) -> None:
        self.log = logging.getLogger(__name__)
        self.nats_client = nats_client
        self.endpoints = endpoints
        self.proxies = proxies
        self._cache_lock = asyncio.Lock()

    @property
    def switch(self) -> dict[str, HomeDeviceListEntry]:
        return self.endpoints.get('switch', {})

    @property
    def app(self) -> dict[str, HomeDeviceListEntry]:
        return self.endpoints.get('app', {})

    @property
    def device(self) -> dict[str, HomeDeviceListEntry]:
        return self.endpoints.get('device', {})

    def __iter__(self) -> Iterator[HomeDeviceListEntry]:
        """Iterate over all endpoints in the HOME Devices list.

        Yields:
            Iterator[HomeDeviceListEntry]: HOME Device List endpoint data
        """
        return iter(
            dev for devs in self.endpoints.values() for dev in devs.values()
        )

    def __len__(self) -> int:
        """Get the total number of endpoints in the HOME Devices list.

        Returns:
            int: The total number of endpoints
        """
        return sum(len(devs) for devs in self.endpoints.values())

    def __getitem__(self, device_id: str) -> HomeDeviceListEntry:
        """Get a device from the device or app cache by its device ID.

        Args:
            device_id (str): The ID of the device to retrieve.

        Returns:
            HomeDeviceListEntry: The device entry if found, else raises KeyError.
        """
        device = self.device.get(device_id) or self.app.get(device_id) or self.switch.get(device_id)
        if not device:
            raise KeyError(f"Device with ID '{device_id}' not found.")
        return device

    def _get_type(self, device: HomeDeviceListEntry) -> str:
        """Determine the type of a device based on its flags.

        Args:
            device (HomeDeviceListEntry): The device to check.

        Returns:
            str: The type of the device ('switch', 'app', or 'device').
        """

        if device.flags.get('IsNetworkSwitch', None):
            return 'switch'
        elif device.flags.get('IsHomeApp', None):
            return 'app'
        else:
            return 'device'

    async def _add_to_cache(self, device: HomeDeviceListEntry) -> None:
        """Add a device to the endpoints cache list.

        Args:
            device (HomeDeviceListEntry): The device to add to the cache.
        """

        async with self._cache_lock:
            self.endpoints[self._get_type(device)][device.home_id] = device

    async def _remove_from_cache(self, device: HomeDeviceListEntry) -> None:
        """Remove a device from the endpoints cache list by its device ID."""

        try:
            model, info = next(
                (model, info) for model, devices in self.endpoints.items()
                for info in devices.values() if info.home_id == device.home_id
            )
        except StopIteration:
            self.log.debug(f"Failed to find '{device.home_id}' in endpoints cache")
            return

        async with self._cache_lock:
            del self.endpoints[model][info.home_id]

    async def _create_model(self, device_id: str, nats_client: Client) -> LawoHomeNativeDevice:
        """Create a LawoHomeNativeDevice object for the given device ID.

        Args:
            device_id (str): The HOME ID of the device to modelled.

        Raises:
            KeyError: If the device is not found.

        Returns:
            LawoHomeNativeDevice: A LawoHomeNativeDevice for the given device ID.
        """

        try:
            info = next(info for info in self.filter(home_id=device_id))
        except StopIteration as err:
            raise DeviceNotFoundError(f"Endpoint with ID '{device_id}' not found.") from err
        finally:
            obj = prepare_model_object(info.model, nats_client=nats_client)
            obj.guid = info.guid
            return await populate_model_object(obj)

    def create_native(self, device_id: str) -> LawoHomeNativeDevice:
        """Synchronous wrapper to create a LawoHomeNativeDevice object for the given device ID.

        Args:
            device_id (str): The ID of the device to retrieve.
        """
        return asyncio.run(self._create_model(device_id, self.nats_client))

    async def create_natives(
        self,
        device_ids: list[str],
        nats_client: Client | None = None
    ) -> dict[str, LawoHomeNativeDevice]:
        """Create LawoHomeNativeDevice objects for a list of HOME device IDs.

        Args:
            device_ids (list[str]): A list of device IDs to create LDF models for.

        Returns:
            dict[str, LawoHomeNativeDevice]: A dictionary mapping device IDs to LawoHomeNativeDevice objects.

        Example:
            natives = await hoc.endpoints.create_natives([
                "yM3373te2eAEWB2qeUL8dA",
                "another_device_id",
            ])
            for device_id, device in natives.items():
                print(f"Created device model for {device_id}: {device}")
        """

        nc = self.nats_client if not nats_client else nats_client
        async with self.nats_client:
            results = await asyncio.gather(
                *[self._create_model(device_id, nats_client=nc) for device_id in device_ids],
                return_exceptions=True
            )

        # Handle the coro returns / exceptions for each ID
        devices = {}
        for device_id, result in zip(device_ids, results):
            if isinstance(result, UnknownDeviceError):
                self.log.error(f"Attempted to create unknown device type: {result}", exc_info=result)
            elif isinstance(result, GetEndpointError):
                # Usually raised when supplied device ID is offline, throw error but do not fail
                self.log.warning(result)
            elif isinstance(result, Exception):
                self.log.error(
                    f"!!! Unknown error during production {device_id}: {result}",
                    exc_info=result
                )
            elif isinstance(result, LawoHomeNativeDevice):
                devices[device_id] = result

        device_strs = "\n\t- ".join(str(dev) for dev in devices.values())
        self.log.info(f"Produced Models: \n\t- {device_strs}")
        return devices

    def filter(self, **criteria: Any) -> Iterator[HomeDeviceListEntry]:
        """Filter the endpoints cache by given criteria.

        Args:
            **criteria: Arbitrary keyword arguments corresponding to HomeDeviceListEntry attributes.

        Returns:
            list[HomeDeviceListEntry]: A list of devices matching all given criteria.

        Example:
            filtered_devices = hoc.endpoints.filter(model="C100", state="online")
            filtered_devices = hoc.endpoints.filter(label="My Device")
        """

        for device in self:
            if all(getattr(device, key, None) == value for key, value in criteria.items()):
                yield device

    async def purge(self, device_ids: list[str]) -> list[str]:
        """Purge devices from the HOME system by their device IDs
        and block until the devices are removed from the cache (via update).

        Args:
            device_ids (list[str]): The IDs of the devices to purge.

        Returns:
            list[str]: A list of the purged device IDs.
        """

        entries = [entry for entry in self if entry.home_id in device_ids]
        async with self.nats_client:
            tasks = asyncio.gather(
                *[
                    devices_home.devices_purge_one(
                        self.nats_client,
                        entry.home_id
                    ) for entry in entries
                ]
            )
            _ = await tasks  # Call to purge appears to return nothing

        self.log.info(f"Purged {len(entries)} device(s) from HOME system")
        return device_ids

    async def create_proxy(self, label: str, device_type: str, ip_address: str, port: int) -> Entry:
        """Create a proxy device instance on the target HOME system

        Args:
            label (str): The label for the proxy device
            device_type (str): The type of device to create (e.g., 'Switch', 'C100', LCU, etc.)
            ip_address (str): The IP address of the target proxy device
            port (int): The port number on the target proxy device
        """

        created = await create_home_proxy_device(
            self.nats_client,
            label=label,
            proxy_type=device_type,
            ip_address=ip_address,
            port=port
        )
        await self.wait_for(match_by='label', match_value=label)
        self.log.info(f"Registered HOME Device: {device_type} {ip_address}:{port}")
        return created

    async def remove_proxies(self, device_ids: list[str]) -> list[str]:
        """Delete proxy device instances from the target HOME system

        Args:
            device_ids (list[str]): The HOME IDs of the proxy devices to delete.
        """

        removed = await remove_home_proxy_device(
            self.nats_client,
            device_ids=device_ids
        )

        await asyncio.gather(
            *[
                self.wait_for(
                    match_by='home_id',
                    match_value=dev_id,
                    invert=True
                ) for dev_id in removed
            ]
        )
        self.log.info(f"Removed device proxy registrations: {removed}")
        return removed

    async def wait_for(
            self,
            match_by: str,
            match_value: str,
            timeout: int = 30,
            invert: bool = False
    ) -> HomeDeviceListEntry | None:
        """Wait for a device to appear (or disappear) in the endpoints cache by attribute.

        Args:
            match_by (str): The HomeDeviceListEntry (DeviceStatus) attribute of the device to wait for.
            match_value (str): The value to match against the specified attribute.
            timeout (int, optional): The maximum time to wait in seconds. Defaults to 30.
            invert (bool, optional): If True, wait for an attribute to NOT appear in cache. Defaults to False.

        Raises:
            TimeoutError: If the device does not appear within the timeout period.
            ValueError: If the specified attribute does not exist on HomeDeviceListEntry.

        Returns:
            HomeDeviceListEntry: The device information once it appears in the cache.
        """

        for _ in range(timeout * 4):  # Check every 0.25s up to timeout
            try:
                info = next(
                    info for info in self if getattr(info, match_by) == match_value
                )
                self.log.debug(f"Found {match_by} '{match_value}' in {info}")
                return info
            except StopIteration:
                if invert:
                    self.log.debug(
                        f"Inverted wait, {match_by} '{match_value}' not found (expected)"
                    )
                    return None
                await asyncio.sleep(0.25)
            except AttributeError as err:
                raise ValueError(
                    f"Invalid attribute '{match_by}' for HomeDeviceListEntry"
                ) from err
        raise TimeoutError(f"Timeout waiting for {match_by} {match_value} to appear in endpoints cache.")

    def to_dict(self) -> dict[str, dict[str, str | dict]]:
        return {x.home_id: x.__dict__ for x in self}

    async def cb_device_update(self, msg) -> None:
        status = DeviceStatus()
        status.MergeFromString(msg.data)
        endpoint = create_home_device_list_entry(status)
        op = msg.subject.split(".")[-1]
        self.log.debug(f"[update] {op.capitalize()} device: {endpoint.home_id}")
        match op:
            case "insert" | "change":
                await self._add_to_cache(endpoint)
            case "remove":
                await self._remove_from_cache(endpoint)
            case _:
                self.log.warning(f"Unexpected Device Update: ({op}, {msg.subject})")
