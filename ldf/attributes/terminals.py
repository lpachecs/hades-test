import asyncio
import logging
import time
from typing import Iterable

from datamodel.endpoints import endpoints_home, endpoints_pb2

CONNECTION_UPDATE_TIMEOUT = 3


def create_terminal_connection(src: str, dst: str) -> endpoints_pb2.InternalConnection:
    """Create an Internal Terminals Connection object

    Args:
        src (str): ID of the terminal to be used as source
        dst (str): ID of the terminal to be used as destination

    Returns:
        endpoints_pb2.InternalConnection: A data structure describing the IO terminal connection.
    """

    connection = endpoints_pb2.InternalConnection()
    connection.SrcID = src
    connection.DstID = dst
    return connection


def sort_terminals(
    terminals: Iterable[endpoints_pb2.InternalTerminal],
    essence: str | None,
    direction: str | None,
    real_input_only=False
) -> list[endpoints_pb2.InternalTerminal]:
    """Apply filtering and sorting to a list of incomming device internal terminal data

    Args:
        terminals (Iterable[endpoints_pb2.InternalTerminal]): List of terminals to sort
        essence (str): Filter by terminal essence type
        direction (str): Filter by terminal direction

    Returns:
        list[endpoints_pb2.InternalTerminal]: Filtered list of internal terminals sorted by Index
    """

    terms = [x for x in terminals]
    if essence:
        terms = [x for x in terms if x.Class == essence]
    if direction == 'tx':
        terms = [x for x in terms if not x.IsDest]
    elif direction == 'rx':
        terms = [x for x in terms if x.IsDest]

    if real_input_only:
        terms = [x for x in terms if x.Class != "IP"]

    return sorted(terms, key=lambda x: x.Index)


class LawoHomeNativeTerminals:

    def __init__(self, device) -> None:
        self.device = device
        self.log = logging.getLogger(__name__)

    def __call__(
        self,
        essence: str | None = None,
        direction: str | None = None,
        no_ip=False
    ) -> list[endpoints_pb2.InternalTerminal]:
        """Return all Internal Terminals currently stored in the local endpoint cache

        Args:
            essence (str | None, optional): Essence type of the terminal. Defaults to None.
            direction (str | None, optional): Terminal is 'tx' or 'rx'. Defaults to None.

        Returns:
            Iterable[endpoints_pb2.InternalTerminal]: All Internal Terminals matching the supplied criteria.
        """

        return sort_terminals(
            self.device.endpoint.Terminals,
            essence,
            direction,
            real_input_only=no_ip
        )

    async def get(
            self,
            essence: str | None = None,
            direction: str | None = None,
            no_ip=False
    ) -> Iterable[endpoints_pb2.InternalTerminal]:
        """Requests IO terminals information from the device (bypass local endpoint cache).

        Returns:
            Iterable[endpoints_pb2.InternalTerminal]: All device terminals data.
        """

        all_terminals, _ = await endpoints_home.endpoints_get_internal_terminals(
            self.device.client,
            self.device.id
        )
        return sort_terminals(all_terminals, essence, direction, real_input_only=no_ip)

    def connections(self) -> Iterable[endpoints_pb2.InternalConnection]:
        """Return the IO terminal connection data from the local endpoint cache.

        Yields:
            Iterable[endpoints_pb2.InternalConnection]: All device terminal connections
        """
        for conn in self.device.endpoint.Connections:
            yield conn

    async def connect(self, terminal_conns: list[tuple[str, str]]):
        """Connects IO routing connections based on Src / Dst terminal IDs.

        Args:
            terminal_conns (list[tuple[str, str]]): A list of Src.ID and Dst.ID tuples.
        """

        await endpoints_home.endpoints_set_internal_connections(
            self.device.client,
            self.device.id,
            [create_terminal_connection(src=x[0], dst=x[1]) for x in terminal_conns]
        )

        self.log.info(f"Waiting for {len(terminal_conns)} InternalTerminal updates")
        await asyncio.gather(
            *[self.wait_for_connection(conn[0], conn[1]) for conn in terminal_conns]
        )

    async def disconnect(self, terminals: list[str]):
        """Disconnects IO routing connections based on terminal IDs.

        Args:
            terminals (list[str]): A list of Rx terminal IDs to disconnect.
        """

        await endpoints_home.endpoints_set_internal_connections(
            self.device.client,
            self.device.id,
            [create_terminal_connection(src="", dst=x) for x in terminals]
        )
        self.log.info(f"Waiting for {len(terminals)} InternalTerminal updates")
        await asyncio.gather(
            *[self.wait_for_connection("", dst) for dst in terminals]
        )

    async def disconnect_all(self) -> bool:
        """Disconnects all IO routing connections on the device"""

        err = await endpoints_home.endpoints_delete_all_internal_connections(
            self.device.client,
            self.device.id
        )
        if not err:
            await asyncio.gather(
                *[self.wait_for_connection("", conn.DstID) for conn in self.connections()]
            )
            return True
        else:
            self.log.error(f"Failed to disconnect all terminals: {err}")
            return False

    async def wait_for_connection(self, src_id: str, dst_id: str) -> None:
        """Block until the endpoint.Connections update is received"""

        tn = time.perf_counter()
        perf = time.perf_counter() - tn
        while src_id not in [x.SrcID for x in self.connections() if x.DstID == dst_id]:
            if perf > CONNECTION_UPDATE_TIMEOUT:
                raise TimeoutError(
                    f"Update not received within {CONNECTION_UPDATE_TIMEOUT}s: {src_id} -> {dst_id}"
                )
            else:
                await asyncio.sleep(0.1)
                perf = time.perf_counter() - tn

        self.log.info(f"Connection update for ({src_id} -> {dst_id}) took: {perf}")
