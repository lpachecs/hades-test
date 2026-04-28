import asyncio
import logging
import time

from datamodel.addresses import addresses_home
from datamodel.addresses.addresses_pb2 import Address
from datamodel.sords.sords_pb2 import Essence, Gate

from ldf.common.system.addresses import (HomeControllerAddress,
                                         create_address_connection,
                                         create_home_controller_address)

CONNECTION_TIMEOUT = 6


class AddressConnectError(Exception):
    """Raised when the an error is returned from the connect request"""

    def __init__(self, msg: str = ''):
        self.msg = msg

    def __str__(self):
        return self.msg


def sort_addresses(
        addresses: list[HomeControllerAddress],
        type: str | None = None,
        direction: str | None = None
) -> list[HomeControllerAddress]:
    """Apply filtering and sorting to a sequence of datamodel Addresses

    Args:
        addresses (list[HomeControllerAddress]): Sequence of Addresses
        type (str, optional): Filter by address type. Defaults to None.
        direction (str, optional): Filter by address direction. Defaults to None.

    Returns:
        list[HomeControllerAddress]: _description_
    """

    if type:
        addresses = [x for x in addresses if x.essence == type]
    if direction == 'tx':
        addresses = [x for x in addresses if not x.is_dest]
    elif direction == 'rx':
        addresses = [x for x in addresses if x.is_dest]
    return sorted(addresses, key=lambda x: x.home_id)


class LawoHomeNativeAddresses:

    def __init__(self, device):
        self.device = device
        self.state = {}
        self.log = logging.getLogger(self.device.label)

    def __call__(self, type=None, direction=None, label: str | None = None) -> list[HomeControllerAddress]:
        """Request all addresses from the device and return a filtered list if required

        Args:
            type (str, optional): Type of address to return (audio, video, gpio, meta). Defaults to None.
            direction (str, optional): Specified direction (tx, rx). Defaults to None.
            label (str, optional): Specific address label to return. Defaults to None.

        Returns:
            list[HomeControllerAddress]: Iterable object containing all devices addresses matching any search criteria
        """
        addrs = [
            create_home_controller_address(addr) for addr in self.state.values()
        ]
        if not label:
            return sort_addresses(addrs, type=type, direction=direction)
        else:
            return [addr for addr in addrs if label == addr.home_id]

    async def _sync_state(self) -> None:
        """Recreates the Addresses state dict with realtime data"""

        addrs, _, err = await addresses_home.addresses_get_one(
            self.device.client,
            self.device.id,
            argStreamToTopic=""
        )
        if err:
            self.log.error(f"!!! Error getting addresses: {err}")
        else:
            self.state = {
                addr.ID: addr for addr in addrs
            }

    async def _wait_for_connection(self, src_label: str, dst_label: str) -> None:
        """Blocks until the expected destination label is updated in the source PeerIDs

        Args:
            src_label (str): Source label of the connection to wait for
            dst_label (str): Destination label of the connection to wait for

        Raises:
            AddressConnectError: Raised if the expected connection updates were not received within timeout
        """

        tn, perf = time.perf_counter(), 0.0
        while dst_label not in [peer for peer in self.state.get(src_label).PeerIDs]:
            perf = time.perf_counter() - tn
            if perf > CONNECTION_TIMEOUT:
                self.log.error(f"!!! GATE: {self.state.get(src_label)}")
                raise AddressConnectError(
                    "The expected source address updates were not received in time."
                )
            else:
                await asyncio.sleep(0.1)

        self.log.info(f"Connected: {src_label} >> {dst_label} in {perf:.2f}s")

    async def _wait_for_disconnection(self, dst_label: str) -> None:
        """Blocks until the PeerIDs of a single address gate is empty

        Args:
            dst_label (str): Label of a single destination address gate expected to be empty

        Raises:
            AddressConnectError: Raised if the PeerID of the gate is not empty within timeout

        """

        tn, perf = time.perf_counter(), 0.0
        try:
            while len(self.state.get(dst_label).PeerIDs):
                perf = time.perf_counter() - tn
                if perf > CONNECTION_TIMEOUT:
                    raise AddressConnectError(
                        f"The expected PeerID updates were not received in time for {dst_label}"
                    )
                else:
                    await asyncio.sleep(0.1)
        except AttributeError:
            # Destination does have PeerIDs, already disconnected
            pass

        self.log.info(f"Disconnected: {dst_label} in {perf:.2f}s")

    async def connect(
        self,
        conns: list[tuple[Gate, Gate]],
        event: asyncio.Event | None = None,
        block_until_connect: bool = True
    ) -> list[tuple[str, str]]:
        """Make connections between multiple source and destiantion gates

        Args:
            conns (list[tuple[sords_pb2.Gate, sords_pb2.Gate]]): A list of tuples containing src, dest gates
            event (asyncio.Event, optional): Event object to flag as done when connections are made. Defaults to None.

        Raises:
            AddressConnectError: The requested connection updates were not received within the expected time

        Returns:
            list[tuple[str, str]]: A list of tuples containing label formatted strings of the connections sent
        """

        tasks = asyncio.gather(
            *[create_address_connection(conn[0], conn[1]) for conn in conns]
        )
        connections = await tasks
        if len(connections) == 0:
            raise AddressConnectError("No connections to connect!")
        else:
            err = await addresses_home.addresses_connect(
                self.device.client,
                connections
            )
            if err:
                self.log.error(err)
                raise AddressConnectError(err)

        connection_labels = [
            (
                ":".join([conn.Src.DevID, conn.Src.SordID, conn.Src.FlowID]),
                ":".join([conn.Dst.DevID, conn.Dst.SordID, conn.Dst.FlowID])
            ) for conn in connections
        ]

        if block_until_connect:
            # Block until source PeerIDs are updated
            await asyncio.gather(
                *[self._wait_for_connection(src, dst) for src, dst in connection_labels]
            )

        if event:
            event.set()
        return connection_labels

    async def disconnect(
        self,
        gates: list[Gate],
        event: asyncio.Event | None = None,
        block_until_disconnect: bool = True
    ) -> bool:
        """ Will disconnect Address Gates given a list of Gates

        Args:
            conns (list[sords_pb2.Gate]):
                A list containing sord_pb2.Gate. Does a regular disconnect using only the Gate
            event (asyncio.Event, optional):
                Event to set. Defaults to None.

        Returns:
            bool: Wether or not self.device.addresses.state updated with the expected disconnection
                  (The corresponding peer IDs of diconnected gates should be empty)
        """

        if len(gates) == 0:
            self.log.warning("!!! Attempting to disconnect zero connections")

        labels = [
            ":".join([gate.DevID, gate.SordID, gate.FlowID]) for gate in gates
        ]

        # Disconnect the gates and block until disconnected
        await addresses_home.addresses_disconnect(
            self.device.client,
            gates
        )

        if block_until_disconnect:
            await asyncio.gather(
                *[self._wait_for_disconnection(dst) for dst in labels]
            )

        if event:
            event.set()
        return True

    def by_sord_id(self, sord_id: str, essence: Essence = None) -> list[Address]:
        """Find all device addresses for a given sord ID, optionally provide an essence type to filter result.

        Args:
            sord_id (str): Sord ID for the desired addresses
            essence (sords_pb2.Essence, optional): Type of addressese to be returned. Defaults to None.

        Returns:
            list[addresses_pb2.Address]: All Addresses associated with the supplied sord ID
        """

        addrs = [
            addr for addr in self.state.values() if addr.Gate.SordID == sord_id
        ]
        if essence:
            addrs = [a for a in addrs if a.Essence == essence]
        self.log.debug(f"Matched Addresses for {sord_id}: {addrs}")
        return addrs
