import asyncio
import logging

from datamodel.client.client import Client
from datamodel.ctls import ctls_pb2
from datamodel.endpoints import endpoints_home, endpoints_pb2

log = logging.getLogger(__name__)


async def listen_for_endpoint_call_home(home_addrs: list[str], num_collect=1):
    """Listen for endpoint calls to HOME and collect their IP addresses.

    This function works for scenarios where the Call HOME is triggered from the HOME UI
    and also when the "Call HOME" button is pressed on the endpoint itself.

    Args:
        client_addrs (list[str]): List of HOME Server IP addresses to listen on.
        num_collect (int, optional): Number of unique IP addresses to collect. Defaults to 1.

    Returns:
        dict: A dictionary mapping device IDs to their IP addresses.
    """

    address_dict = {}
    c = Client(
        addr=home_addrs,
        port=4222
    )

    async def cb_findme_gcf(msg):

        device_id = msg.subject.split(".")[-2]
        requ = ctls_pb2.UpdateCtlList()
        requ.MergeFromString(msg.data)
        for ctl in requ.Ctls:
            if ctl.oid == "System.Findme" and ctl.value.flag:
                address_dict[device_id] = await _get_network_interface_ips(device_id)

    async def cb_findme_nodesys(msg):
        """Handle FindMe requests from endpoints and return NetworkInterface IP addresses
        of calling devices"""

        device_id = msg.subject.split(".")[-2]
        requ = endpoints_pb2.SetFindMeRequest()
        requ.MergeFromString(msg.data)
        if requ.Enable:
            address_dict[device_id] = await _get_network_interface_ips(device_id)

    async def _get_network_interface_ips(device_id: str):
        """Get the network interface IP addresses for a specific device."""

        networks, err = await endpoints_home.endpoints_get_networks(
            client=c,
            argdevID=device_id
        )
        if err:
            log.error(f"Error getting network interfaces for {device_id}: {err}")
            return []
        return [x.IpAddress for x in networks]

    async with c:
        asyncio.gather(
            c.sub("set.endpoints.*.findme", cb_findme_nodesys),
            c.sub("update.ctls.*.change", cb_findme_gcf)
        )
        while True:
            if len(address_dict) >= num_collect:
                break
            await asyncio.sleep(.2)

    return address_dict
