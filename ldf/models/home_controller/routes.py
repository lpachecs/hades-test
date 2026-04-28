import asyncio
import logging
from typing import Iterator

from datamodel.addresses import addresses_home, addresses_pb2
from datamodel.client.client import Client
from datamodel.endpoints import endpoints_pb2
from datamodel.sw import sw_pb2

from ldf.attributes.interfaces import HomeControllerInterface
from ldf.attributes.sords import LawoHomeNativeSord
from ldf.common.system.addresses import (HomeControllerAddress,
                                         create_address_connection,
                                         create_home_controller_address)
from ldf.common.system.routing import (HomeControllerRoute,
                                       HomeControllerStitch,
                                       create_home_controller_stitch)


class HomeControllerRoutes:

    def __init__(
        self,
        client: Client,
        addrs: list[HomeControllerAddress],
        sords: list[LawoHomeNativeSord],
        stitches: list[HomeControllerStitch],
        interfaces: list[HomeControllerInterface]
    ) -> None:
        self.log = logging.getLogger("HomeControllerRoutes")
        self.client = client
        self._addrs_lock = asyncio.Lock()
        self._sords_lock = asyncio.Lock()
        self._stitches_lock = asyncio.Lock()
        self._sords: list[LawoHomeNativeSord] = sords
        self._stitches = stitches if stitches else []
        self._interfaces = interfaces
        self._addrs: dict[str, HomeControllerAddress] = {
            addr.home_id: addr for addr in addrs
        } if addrs else {}

    @property
    def sources(self) -> list[HomeControllerAddress]:
        return [x for x in self._addrs.values() if x.is_dest is False]

    @property
    def destinations(self) -> list[HomeControllerAddress]:
        return [x for x in self._addrs.values() if x.is_dest is True]

    def __iter__(self) -> Iterator[HomeControllerRoute]:
        return self._active_routes()

    def __len__(self) -> int:
        return len(list(self.__iter__()))

    def _active_sources(self) -> list[HomeControllerAddress]:
        """Return a list of source Addresses with PeerIDs

        Returns:
            list[HomeControllerAddress]: A list of source addresses with peers
        """
        return [x for x in self.sources if x.peers]

    def _active_destinations(self) -> list[HomeControllerAddress]:
        """Return a list of destination Addresses with PeerIDs

        Returns:
            list[HomeControllerAddress]: A list of destination addresses with peers
        """
        return [x for x in self.destinations if x.peers]

    def _active_routes(self) -> Iterator[HomeControllerRoute]:
        """Iterate over all active source addresses and produce a route with path stitch information
        if any destination PeerIDs contains the source home_id.

        Called when `hoc.routes` is iterated over.

        Yields:
            Iterator[HomeControllerRoute]: An iterator over active routes
        """

        # TODO: Path finding is not finished yet - stitches need proper switch path making
        for src in self._active_sources():
            for dst in self._active_destinations():
                if src.home_id in dst.peers:
                    route = HomeControllerRoute(source=src, destination=dst)
                    try:
                        source_sord = next(
                            x for x in self._sords
                            if x.device_id == route.source.device_id and x.ID == route.source.sord_id
                        )
                        dest_sord = next(
                            x for x in self._sords
                            if x.device_id == route.destination.device_id and x.ID == route.destination.sord_id
                        )
                        route.path_pri, route.path_sec = asyncio.run(
                            self._find_path(source_sord, dest_sord)
                        )
                    except Exception as e:
                        self.log.error(f"Pathfinding failed for route {route}: {e}", exc_info=True)
                    finally:
                        yield route
                    break

    async def _add_to_addrs(self, addr: HomeControllerAddress) -> None:
        """Add or update an address in the local Addresses cache"""

        async with self._addrs_lock:
            self._addrs[addr.home_id] = addr

    async def _add_to_sords(self, sord: LawoHomeNativeSord) -> None:
        """Add or update a sord in the local Sords cache"""

        async with self._sords_lock:
            existing = next((x for x in self._sords if x.device_id == sord.device_id and x.ID == sord.ID), None)
            if existing:
                self._sords.remove(existing)
            self._sords.append(sord)

    async def _add_to_stitches(self, stitch: HomeControllerStitch):
        async with self._stitches_lock:
            existing = next(
                (
                    x for x in self._stitches
                    if x.ip_mcast == stitch.ip_mcast and
                    x.iface_input == stitch.iface_input and
                    x.iface_output == stitch.iface_output
                ), None
            )
            if existing:
                self._stitches.remove(existing)
            self._stitches.append(stitch)

    async def _remove_from_addrs(self, addr: HomeControllerAddress) -> None:
        """Remove an address from the local Addresses cache"""

        if addr.home_id in self._addrs:
            async with self._addrs_lock:
                del self._addrs[addr.home_id]

    async def _remove_from_sords(self, sord: LawoHomeNativeSord) -> None:
        """Remove a sord from the local Sords cache"""

        async with self._sords_lock:
            existing = next((x for x in self._sords if x.device_id == sord.device_id and x.pb.ID == sord.pb.ID), None)
            if existing:
                self._sords.remove(existing)

    async def _remove_from_stiches(self, stitch: HomeControllerStitch):
        async with self._stitches_lock:
            existing = next(
                (
                    x for x in self._stitches
                    if x.ip_source == stitch.ip_source and
                    x.ip_mcast == stitch.ip_mcast and
                    x.iface_input == stitch.iface_input and
                    x.iface_output == stitch.iface_output
                ), None
            )
            if existing:
                self._stitches.remove(existing)

    # TODO: Unifinsihed pathfinding code - Must finish!
    async def _find_path(self, src_sord: LawoHomeNativeSord,
                         dst_sord: LawoHomeNativeSord) -> tuple[list[HomeControllerStitch], list[HomeControllerStitch]]:
        """Finds the path of stitches used to route a single HOME sender, receiver pair (route).

        Args:
            src_sord (LawoHomeNativeSord): LDF Sord object that is the source of the HOME route
            dst_sord (LawoHomeNativeSord): LDF Sord object that is the destination of the HOME route

        Returns:
            tuple[list[HomeControllerStitch], list[HomeControllerStitch]]: Tuple of (pri, sec) path of stitches
        """

        # Get PRIMARY + SECONDARY source IP Addresses + Mcast Addrs for each essence flow
        # Get source device Interfaces
        pri_src_origin_ips = set(flow.primary.SrcIpAddr for flow in src_sord.flows)
        pri_src_origin_mcasts = set(flow.primary.McastIpAddr for flow in src_sord.flows)
        sec_src_origin_ips = set(flow.secondary.SrcIpAddr for flow in src_sord.flows)
        sec_src_origin_mcasts = set(flow.secondary.McastIpAddr for flow in src_sord.flows)
        pri_src_iface = next(iface for iface in self._interfaces if iface.ip_address in pri_src_origin_ips)
        sec_src_iface = next(iface for iface in self._interfaces if iface.ip_address in sec_src_origin_ips)

        # Get PRIMARY + SECONDARY destination IP Addresses
        # Get destination device Interfaces
        pri_dst_origin_ips = set(flow.primary.SrcIpAddr for flow in dst_sord.flows)
        sec_dst_origin_ips = set(flow.secondary.SrcIpAddr for flow in dst_sord.flows)
        pri_dst_iface = next(iface for iface in self._interfaces if iface.ip_address in pri_dst_origin_ips)
        sec_dst_iface = next(iface for iface in self._interfaces if iface.ip_address in sec_dst_origin_ips)

        # All Stitches for RED / BLUE legs of redundant flow
        red_stitches = [stitch for stitch in self._stitches if stitch.ip_mcast in pri_src_origin_mcasts]
        blue_stitches = [stitch for stitch in self._stitches if stitch.ip_mcast in sec_src_origin_mcasts]

        async def follow_path(mcast_stitches, source_iface, dest_iface):
            current_hop = source_iface
            while True:
                # Find stitch where `current_hop` iface is src
                # and append to path
                try:
                    current_stitch = next(
                        stitch for stitch in mcast_stitches
                        if stitch.switch_id == current_hop.lldp.chassis_id and
                        stitch.iface_input == current_hop.lldp.port_id
                    )
                    self.log.info(f"UPDATED CURRENT STITCH: {current_stitch}")
                except StopIteration:
                    self.log.error(f"Unable to find stitch entry with src interface: {current_hop}")
                    raise
                finally:
                    yield current_stitch

                # Find dst interface of the current stitch
                # and assign to `current_hop`
                try:
                    current_hop = next(
                        iface for iface in self._interfaces
                        if iface.chassis_id == current_stitch.switch_id and     # switch id (chassis-id)
                        iface.iface_media == current_stitch.iface_output        # interface (port-id)
                    )
                    self.log.info(f"UPDATED CURRENT HOP: {current_hop}")
                except StopIteration:
                    self.log.error(f"Unable to determine next hop interface using stitch destiantion: {current_stitch}")
                    raise
                finally:
                    # TODO: Need to find the Dstination interface and check isLastHop before break
                    if current_hop == dest_iface:
                        break
        try:
            pri_path = [x async for x in follow_path(red_stitches, pri_src_iface, pri_dst_iface)]
            sec_path = [x async for x in follow_path(blue_stitches, sec_src_iface, sec_dst_iface)]
        except Exception as err:
            self.log.error(f"Path failed: {err}")
            # pri_path, sec_path = red_stitches, blue_stitches
            pri_path, sec_path = [], []
        finally:
            return pri_path, sec_path

    async def create(
        self,
        conns: list[tuple[HomeControllerAddress, HomeControllerAddress]]
    ) -> list[HomeControllerRoute]:
        """Create HOME Address connections for multiple sources and destinations

        Args:
            conns (list[tuple[HomeControllerAddress, HomeControllerAddress]]): List of source-destination pairs

        Returns:
            list[HomeControllerRoute] | None: The created routes
        """

        connections = await asyncio.gather(
            *(create_address_connection(src.gate, dst.gate) for src, dst in conns)
        )

        async with self.client:
            err = await addresses_home.addresses_connect(self.client, connections)
            if err:
                self.log.error(f"Failed to create route: {err}")
            # TODO: Wait for addresses to update before returning
            routes = [
                HomeControllerRoute(source=src, destination=dst)
                for src, dst in conns
            ]
            return routes

    async def disconnect(self, routes: list[HomeControllerRoute]) -> None:
        """Disconnect multiple active routes"""

        async with self.client:
            err = await addresses_home.addresses_disconnect(
                self.client,
                [x.destination.gate for x in routes]
            )
        if err:
            raise Exception(f"Failed to disconnect routes: {err}")
        else:
            return

    def filter(self, **kwargs) -> Iterator[HomeControllerAddress | HomeControllerRoute]:

        for match in self.sources + self.destinations + [x for x in self]:
            try:
                if all(getattr(match, key) == value for key, value in kwargs.items()):
                    yield match
            except AttributeError:
                continue

    def to_dict(self) -> list[dict]:
        return [addr.to_dict() for addr in self]

    async def cb_update_addrs(self, msg) -> None:
        """Callback to handle system Address updates from NATS subscriptions

        All incomming subscription data is used to update the local Addresses cache
        """

        op = msg.subject.split(".")[-1]
        update = addresses_pb2.Update()
        update.MergeFromString(msg.data)
        self.log.debug(f"[update] {op.capitalize()} addresses: {op} {len(update.Addresses)} addresses")
        for address in update.Addresses:
            addr = create_home_controller_address(address)
            self.log.debug(f"[update] - {addr.home_id} | {addr.caps} | Peers: {addr.peers}")
            match op:
                case "insert" | "change":
                    await self._add_to_addrs(addr)
                case "remove":
                    await self._remove_from_addrs(addr)
                case _:
                    self.log.warning(f"Unknown address update operation: {op}")

    async def cb_update_sords(self, msg) -> None:
        """Callback to handle system Sord updates from NATS subscriptions"""

        op = msg.subject.split(".")[-1]
        ep = endpoints_pb2.Endpoint()
        ep.MergeFromString(msg.data)
        sords = [x for x in ep.Sords]
        self.log.info(f"[update] {op.capitalize()} {len(sords)} sords from {ep.ID}")
        match op:
            case "insert" | "change":
                for sord in sords:
                    await self._add_to_sords(LawoHomeNativeSord(sord, ep.ID))
            case "remove":
                for sord in sords:
                    await self._remove_from_sords(LawoHomeNativeSord(sord, ep.ID))

    async def cb_update_stitches(self, msg) -> None:
        """Callback to handle system Stitch updates from NATS subscriptions"""

        op = msg.subject.split(".")[-1]
        update = sw_pb2.StitchesUpdate()
        update.MergeFromString(msg.data)
        stitches = [x for x in update.Stitches]
        self.log.info(f"[update] {op.capitalize()} {len(stitches)} stitches:")
        for stitch_upd in update.Stitches:
            stitch = create_home_controller_stitch(stitch_upd)
            self.log.info(f"""[update] - {stitch.switch_id} | {stitch.ip_mcast}
                          ({stitch.ip_source}) | {stitch.iface_input} -> {stitch.iface_output}""")
            match op:
                case "insert" | "change":
                    await self._add_to_stitches(stitch)
                case "remove":
                    await self._remove_from_stiches(stitch)
                case _:
                    self.log.warning(f"Unhandled stitch update: {update}")
