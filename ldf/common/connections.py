from datamodel.sords.sords_pb2 import Essence, Gate

from ldf.attributes.sords import LawoHomeNativeFlow, LawoHomeNativeSord
from ldf.models.base import LawoHomeNativeDevice


async def connect_sords(
        src_map:
        dict[LawoHomeNativeDevice: list[LawoHomeNativeSord]],
        dst_map:
        dict[LawoHomeNativeDevice: list[LawoHomeNativeSord]],
        block_until_connect=True
) -> list[tuple[str, str]]:
    """

    Connects device Sords

    The number of TX and RX sords must be equal, however,
    if only a single TX sord is given it will be patched to all RX

    Args:
        src_map (dict[LawoHomeNativeDevice: list[LawoHomeNativeSord]]):
            A dict where the key is the device and the value is the TX sords
        dst_map (dict[LawoHomeNativeDevice: list[LawoHomeNativeSord]]):
            A dict where the key is the device and the value is the RX sords

    Returns:
        list[tuple[str, str]]: A list of connections represented in strings

    Examples:
        connect_sords(
            {
                device_1: [tx_1, tx_2, tx_1],
                device_2: [tx_3, tx_4]
            },
            {
                device_3: [rx_1, rx_2],
                device_4: [rx_3, rx_4, rx_5]
            }
        )

        The following conections would be made:

            - device_1 : tx_1 > device_3 : rx_1
            - device_1 : tx_2 > device_3 : rx_2
            - device_1 : tx_1 > device_4 : rx_3
            - device_2 : tx_3 > device_4 : rx_4
            - device_2 : tx_4 > device_4 : rx_5

        You could think of all lists in the src_map and dst_map
        as two seperate lists which get mapped 1:1:

            [tx_1, tx_2, tx_1, tx_3, tx_4]
               |     |     |     |     |
               v     v     V     V     V
            [rx_1, rx_2, rx_3, rx_4, rx_5]
    """
    # Ensure that the number of TX/RX sords are equal
    total_src = sum(len(sords) for sords in src_map.values())
    total_dst = sum(len(sords) for sords in dst_map.values())
    if total_src == 1:
        src_map = {
            next(iter(src_map.keys())):
                next(iter(src_map.values())) * total_dst}
    else:
        assert total_src == total_dst, (
            f"Number of TX/RX sords are not equal ({total_src}:{total_dst})")
    # Make connections
    idx = 0
    flattened_dst_map = [(d, s) for d, sords in dst_map.items() for s in sords]
    for src_device, src_sords in src_map.items():
        sords_to_connect = []
        for src_sord in src_sords:
            dst_device, dst_sord = flattened_dst_map[idx]
            sords_to_connect.append((src_sord, dst_device, dst_sord))
            idx += 1
        gates = get_gates_from_data(src_device, sords_to_connect)
        async with src_device:
            await src_device.addresses.connect(gates, block_until_connect=block_until_connect)


def get_gates_from_data(src_device: LawoHomeNativeDevice,
                        sords_to_connect: list
                        ) -> list[tuple[Gate, Gate]]:
    """ Will connect all valid flow address gates in a Sord

    Args:
        src_device (LawoHomeNativeDevice): The transmitting device
        sords_to_connect (list): An organised list of destinarion nfo

    Returns:
        list[tuple[Gate, Gate]]: The Gate connections to make
    """
    gates = []
    for src_sord, dst_device, dst_sord in sords_to_connect:
        for essence in Essence.values():
            if essence is Essence.NONE:
                continue
            # Make possible flow connections by essence
            src_flows = [
                flow for flow in src_sord.flows if flow.essence == essence]
            dst_flows = [
                flow for flow in dst_sord.flows if flow.essence == essence]
            # If either cannot send/recv then continue
            if not src_flows or not dst_flows:
                continue
            for src_flow, dst_flow in zip(src_flows, dst_flows):
                gates.append(
                    (
                        src_device.addresses.state[f"{src_device.id}:{src_sord.ID}:{src_flow.ID}"].Gate,
                        dst_device.addresses.state[f"{dst_device.id}:{dst_sord.ID}:{dst_flow.ID}"].Gate,
                    )
                )
    return gates


async def disconnect_destinations(
    disconnections:
    dict[LawoHomeNativeDevice: list[LawoHomeNativeSord or LawoHomeNativeFlow]],
    block_until_disconnect=True
):
    """ Will disconnect RX Sords/Flows of a device

    Args:
        device (dict[LawoHomeNativeDevice, list[LawoHomeNativeSord]]):
            A dictionary where the key is the device and
            the values are a list of Sords/Flows to disconnect

    Returns:
        bool: True if the disconnect was sucessful
    """

    for device, destinations in disconnections.items():
        async with device:
            gates = []
            for dst in destinations:
                if type(dst) is LawoHomeNativeSord:
                    for flow in dst.flows:
                        gates.append(
                            device.addresses.state[f"{device.id}:{dst.ID}:{flow.ID}"].Gate
                        )
                if type(dst) is LawoHomeNativeFlow:
                    gates.append(
                        device.addresses.state[
                            f"{device.id}:{dst.parent.ID}:{dst.ID}"].Gate)
            await device.addresses.disconnect(gates, block_until_disconnect=block_until_disconnect)
