from dataclasses import dataclass
from typing import AsyncGenerator

from datamodel.addresses import addresses_home, addresses_pb2
from datamodel.client.client import Client
from datamodel.sords import sords_pb2


@dataclass
class HomeControllerAddress:
    pb: addresses_pb2.Address
    home_id: str
    device_id: str
    sord_id: str
    flow_id: str
    model: str
    labels: list[str]
    location: str
    is_dest: bool
    status: str
    essence: str
    encap: str
    caps: list[str]
    gate: sords_pb2.Gate
    peers: list[str]

    def __str__(self) -> str:
        return f"<{self.home_id} - {' '.join(self.labels + [])}>"


def create_home_controller_address(addr: addresses_pb2.Address) -> HomeControllerAddress:
    """Create a properly formatted HomeControllerAddress object from a datamodel Address

    Args:
        addr (addresses_pb2.Address): The datamodel Address object to marshal into ControllerAddress

    Returns:
        HomeControllerAddress: A correctly formatted HomeControllerAddress object.
    """

    return HomeControllerAddress(
        pb=addr,
        home_id=addr.ID,
        device_id=addr.Gate.DevID,
        sord_id=addr.Gate.SordID,
        flow_id=addr.Gate.FlowID,
        is_dest=addr.IsDest,
        model=addr.Model,
        labels=[x for x in addr.Labels],
        location=addr.Location,
        status=addresses_pb2.Status.Name(addr.Status).lower(),
        essence=sords_pb2.Essence.Name(addr.Essence).lower(),
        encap=sords_pb2.Encap.Name(addr.Encap),
        caps=[x for x in addr.Caps],
        gate=addr.Gate,
        peers=addr.PeerIDs
    )


async def collect_addresses(nats_client: Client) -> AsyncGenerator[HomeControllerAddress, None]:
    """Iterate through all addresses in the HOME system"""

    async def addresses_list():
        addrs, num, err = await addresses_home.addresses_get_all(nats_client, "")
        if err:
            raise Exception(f"Failed to get addresses list: {err}")
        else:
            return addrs

    for addr in await addresses_list():
        yield create_home_controller_address(addr)


async def create_address_connection(src: sords_pb2.Gate, dst: sords_pb2.Gate) -> addresses_pb2.Connection:
    """Create a HOME addresses_pb2.Connection object from source and destination gates

    Args:
        src (sords_pb2.Gate): sord Gate object of the source flow
        dst (sords_pb2.Gate): sord Gate object of the destination

    Returns:
        addresses_pb2.Connection: The populated connection object
    """

    connection = addresses_pb2.Connection()
    connection.Src.MergeFrom(src)
    connection.Dst.MergeFrom(dst)
    return connection
