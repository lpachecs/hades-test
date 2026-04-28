from dataclasses import dataclass, field
from typing import AsyncGenerator

from datamodel.client.client import Client
from datamodel.sw import sw_home, sw_pb2
from nats.errors import NoRespondersError, TimeoutError

from ldf.common.system.addresses import HomeControllerAddress


@dataclass
class HomeControllerStitch:
    switch_id: str
    iface_input: str
    iface_output: str
    ip_source: str
    ip_mcast: str
    pb: sw_pb2.Stitch

    def __repr__(self) -> str:
        return f"<{self.switch_id} {self.iface_input}->{self.iface_output} {self.ip_source} [{self.ip_mcast}]>"


@dataclass
class HomeControllerRoute:
    source: HomeControllerAddress
    destination: HomeControllerAddress
    path_pri: list[HomeControllerStitch] = field(default_factory=list)
    path_sec: list[HomeControllerStitch] = field(default_factory=list)

    def __str__(self) -> str:
        pri_path = "\n".join([f"|{'_' * idx} {node}" for idx, node in enumerate(self.path_pri, start=1)])
        sec_path = "\n".join([f"|{'_' * idx} {node}" for idx, node in enumerate(self.path_sec, start=1)])
        return (
            f"{self.status} {self.source.home_id:<40} -> {self.destination.home_id}\n"
            f"{pri_path}\n"
            f"{sec_path}"
        )

    @property
    def status(self) -> tuple[str, str]:
        return self.source.status, self.destination.status

    def to_dict(self) -> dict:
        return {
            "source": self.source.home_id,
            "destination": self.destination.home_id,
            "status_source": self.source.status,
            "status_destination": self.destination.status,
            "path": ([stitch for stitch in self.path_pri], [stitch for stitch in self.path_sec])
        }


def create_home_controller_stitch(stitch: sw_pb2.Stitch) -> HomeControllerStitch:
    """Create a properly formatted object for HOME stitches in a uniform way across HomeController

    Args:
        stitch (sw_pb2.Stitch): The stitch protobuf message.

    Returns:
        HomeControllerStitch: The formatted HomeControllerStitch object.
    """

    return HomeControllerStitch(
        switch_id=stitch.SwitchDevID,
        iface_input=stitch.InputIface,
        iface_output=stitch.OutputIface,
        ip_source=stitch.SourceIPAddress,
        ip_mcast=stitch.MulticastGroupIP,
        pb=stitch
    )


async def collect_stitches(nats_client: Client, switch_ids: list[str]) -> AsyncGenerator[HomeControllerStitch, None]:
    """Collect stitches for a list of switch IDs.

    Args:
        nats_client (Client): The NATS client to use for communication.
        switch_ids (list[str]): The list of switch IDs to collect stitches for.

    Returns:
        AsyncGenerator[HomeControllerStitch, None]: An asynchronous generator yielding HomeControllerStitch objects.
    """

    for switch_id in switch_ids:
        try:
            stitches, _ = await sw_home.sw_get_stitches(nats_client, switch_id)
        except (NoRespondersError, TimeoutError):
            continue

        for stitch in stitches:
            yield create_home_controller_stitch(stitch)
