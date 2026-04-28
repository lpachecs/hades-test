import logging
from dataclasses import dataclass
from typing import Iterable

from datamodel.endpoints import endpoints_home, endpoints_pb2


@dataclass
class HomeInterfaceLLDP:
    system_name: str
    mgmt_addr: str
    chassis_id: str
    port_id: str
    desc: str

    def __str__(self):
        return f">> {' | '.join([self.system_name, self.mgmt_addr, self.chassis_id, self.port_id])}"


@dataclass
class HomeControllerInterface:
    pb: endpoints_pb2.NetworkInterface
    home_id: str
    mac_address: str
    label: str
    iface_media: str
    lldp: HomeInterfaceLLDP
    chassis_id: str
    ip_address: str | None = None
    subnet_len: int | None = None
    default_gateway: str | None = None

    def __repr__(self):
        return " | ".join([self.home_id, self.mac_address, self.ip_address, str(self.lldp)])


class LawoHomeNativeInterfaces:

    def __init__(self, device):
        self.device = device
        self.log = logging.getLogger(self.device.label)
        self.state: list[HomeControllerInterface] = []

    def __str__(self) -> str:
        """Represent all known interfaces as a short string"""
        return " | ".join([f"{i.label}: {i.ip_address}" for i in self()])

    def __iter__(self):
        self.n = 0
        return self

    def __next__(self):
        try:
            interface = sorted([x for x in self()], key=lambda x: x.home_id)[self.n]
            self.n += 1
            return interface
        except IndexError:
            raise StopIteration

    def __call__(self, interface_id: str | None = None) -> Iterable[HomeControllerInterface]:
        """Get the device endpoint interface objects from the local endpoint cache and return sorted by ID

        Returns:
            Iterable[HomeControllerInterface]: A list of device interfaces. Sorted by ID
        """

        self.state = [create_home_native_interface(iface) for iface in self.device.endpoint.Interfaces]
        if not interface_id:
            return sorted([x for x in self.state], key=lambda x: x.home_id)
        else:
            return [x for x in self.state if x.home_id == interface_id]

    async def get(self) -> Iterable[endpoints_pb2.NetworkInterface]:
        """Get information on the devices network interfaces directly from the device

        Returns:
            list[endpoints_pb2.NetworkInterface]: A list of device interfaces. Sorted by ID
        """

        self.resp, _ = await endpoints_home.endpoints_get_networks(
            self.device.client,
            self.device.id
        )

        return self.resp

    async def set(self, interfaces: list[endpoints_pb2.NetworkInterface]) -> list[str]:
        """Set attributes of multiple network interfaces

        Args:
            interfaces (list[endpoints_pb2.NetworkInterface]): A list of modified network interface objects

        Returns:
            list[str]: A list of modified interface IDs
        """

        ids, _ = await endpoints_home.endpoints_set_networks(
            self.device.client,
            self.device.id,
            interfaces
        )
        return ids


def create_home_native_interface(iface: endpoints_pb2.NetworkInterface):

    return HomeControllerInterface(
        pb=iface,
        home_id=iface.ID,
        mac_address=iface.MacAddress,
        label=iface.Label,
        iface_media=iface.MediaInterface,
        lldp=HomeInterfaceLLDP(
            system_name=iface.LLDP.SystemName,
            mgmt_addr=iface.LLDP.MgmtIpAddress,
            chassis_id=iface.LLDP.ChassisID,
            port_id=iface.LLDP.PortID,
            desc=iface.LLDP.PortDescription,
        ),
        chassis_id=iface.ChassisID,
        ip_address=iface.IpAddress,
        subnet_len=iface.SubnetPrefixLen,
        default_gateway=iface.DefaultGateway
    )
