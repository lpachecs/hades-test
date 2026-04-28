import asyncio
import itertools

import pytest
from datamodel.addresses import addresses_pb2
from datamodel.sords import sords_pb2

from ldf.common.system.addresses import HomeControllerAddress
from ldf.models.base import LawoHomeNativeDevice
from tests import log

SORD_UPDATE_TIMEOUT = 4

pytestmark = pytest.mark.dependency


async def validate_expected_connections(
        device: LawoHomeNativeDevice,
        exp_connections: list[tuple[str, str]],
        event=None
) -> None:
    """Validate a set of expected connections are correctly represented on the expected receiver"""

    async with device:

        log.info(f"Validate receiver ({device.label}) PeerIDs:")
        for src_label, dest_label in exp_connections:
            validate_dest = device.addresses.state[dest_label]
            while not len(validate_dest.PeerIDs) != 0:
                await asyncio.sleep(0.1)

            for peer in validate_dest.PeerIDs:
                assert peer == src_label
                log.info(f"\t{dest_label} << {peer}")

    if event:
        event.set()


@pytest.fixture
async def target_sender_sord(built_test_device, require_audio_sords_target):
    """Inserts a single sender sord from the target device into a test"""

    async with built_test_device.client:
        created_senders, _ = require_audio_sords_target
        return next(x for x in created_senders)


@pytest.fixture
async def reference_receiver_sord(reference_device, require_audio_sords_ref):
    """Inserts a single receiver sord from the reference device into a test"""

    async with reference_device.client:
        _, created_recveivers = require_audio_sords_ref
        return next(x for x in created_recveivers)


@pytest.fixture
async def target_sender_address(built_test_device, target_sender_sord):
    """Inserts a single sender address from the target device into a test"""

    async with built_test_device.client:
        return next(
            x for x in await built_test_device.addresses(direction='tx', type='audio')
            if x.ID.split(":")[-2] == target_sender_sord.ID and x.Essence == sords_pb2.Essence.AUDIO
        )


@pytest.fixture
async def reference_receiver_address(reference_device, reference_receiver_sord):
    """Inserts a single receiver address from the reference device into a test"""

    async with reference_device.client:
        return next(
            x for x in await reference_device.addresses(direction='rx')
            if x.ID.split(":")[-2] == reference_receiver_sord.ID and x.Essence == sords_pb2.Essence.AUDIO
        )


@pytest.fixture
async def require_audio_connection(
    built_test_device,
    reference_device,
    target_sender_address,
    reference_receiver_address
):
    """Creates a single audio connection from test device to a suitable receiver on the reference device.
    Tears down any connection made after test is completed."""

    async with built_test_device:
        required_conn = await built_test_device.addresses.connect(
            [
                (target_sender_address.Gate, reference_receiver_address.Gate)
            ]
        )

    yield required_conn

    async with reference_device:
        await reference_device.addresses.disconnect([reference_receiver_address.Gate])


def test_create_connection_func():
    """Validate attribute function produces correction protobuf type"""

    from ldf.attributes.addresses import create_connection
    source_gate = sords_pb2.Gate()
    destination_gate = sords_pb2.Gate()
    assert type(create_connection(source_gate, destination_gate)) == addresses_pb2.Connection


@pytest.mark.parametrize("address_type", ["audio", "video", "meta", "gpio"])
async def test_get_addresses(built_test_device, address_type):

    async with built_test_device:
        dev_addresses = built_test_device.addresses(type=address_type)

    for dev_address in dev_addresses:
        log.info(dev_address)
        assert isinstance(dev_address, HomeControllerAddress), \
            f"Expected Address type, got {type(dev_address)}"
    log.info(f"{built_test_device.label} reports {len(dev_addresses)} {address_type} addresses")


class TestAudioAddressConnection:

    async def test_connect_single_audio_source_single_audio_destination(
        self,
        built_test_device,
        reference_device,
        target_sender_address,
        reference_receiver_address
    ):
        """Connect a single source address from the test device
        to a single destination addresses on the reference device.

        Validates receiver PeerID updates are received
        """

        async with built_test_device:
            connection_labels = await built_test_device.addresses.connect(
                [(target_sender_address.Gate, reference_receiver_address.Gate)]
            )

        e = asyncio.Event()
        await validate_expected_connections(reference_device, connection_labels, event=e)
        await e.wait()

        async with reference_device:
            await reference_device.addresses.disconnect([reference_receiver_address.Gate])
            await asyncio.sleep(SORD_UPDATE_TIMEOUT)

    async def test_connect_single_audio_source_multiple_audio_destination(
            self,
            built_test_device,
            reference_device,
            target_sender_address,
            require_audio_sords_ref
    ):
        """Connect multiple source addresses from the test device to
        suitible destination addresses on the reference device.

        Validates receiver PeerID updates are received
        """

        async with reference_device:
            _, ref_sords = require_audio_sords_ref
            ref_addresses = await reference_device.addresses(direction='rx')

        required_recv_addresses = [x.Gate for x in ref_addresses
                                   if x.Gate.SordID in [sord.ID for sord in ref_sords]]

        async with built_test_device:
            connections = [(target_sender_address.Gate, dest_gate)
                           for dest_gate in required_recv_addresses]
            connection_labels = await built_test_device.addresses.connect(
                connections
            )

        e = asyncio.Event()
        await validate_expected_connections(reference_device, connection_labels, event=e)
        await e.wait()
        async with reference_device:
            await reference_device.addresses.disconnect(required_recv_addresses)

    async def test_connect_multiple_audio_source_multiple_audio_destination(
            self,
            built_test_device,
            reference_device,
            require_audio_sords_target,
            require_audio_sords_ref
    ):
        """Connect multiple source addresses from the test device to
        suitible destination addresses on the reference device.

        Validates receiver PeerID updates are received
        """

        src_sords, _ = require_audio_sords_target
        _, dst_sords = require_audio_sords_ref

        async with reference_device:
            dst_addresses = [
                x.Gate for x in await reference_device.addresses(direction='rx')
                if x.Gate.SordID in [sord.ID for sord in dst_sords]
            ]

        async with built_test_device:
            src_addresses = [x.Gate for x in await built_test_device.addresses(direction='tx')
                        if x.Gate.SordID in [sord.ID for sord in src_sords]]

            connections = [(src_gate, dest_gate)
                           for src_gate, dest_gate in zip(src_addresses, dst_addresses)]

            connection_labels = await built_test_device.addresses.connect(
                connections
            )

        e = asyncio.Event()
        await validate_expected_connections(reference_device, connection_labels, event=e)
        await e.wait()
        async with reference_device:
            await reference_device.addresses.disconnect(dst_addresses)

    # async def test_connect_single_video_source_single_audio_destination():
    #     pass

    # async def test_connect_single_gpio_source_single_audio_destination():
    #     pass

    # async def test_connect_single_meta_source_single_audio_destination():
    #     pass


async def test_find_address_by_label(built_test_device):
    match_interface = "SdiOut 33"
    match_type = "video"

    if not built_test_device.model == ".edge":
        pytest.xfail("Attempts to match .edge specific port")

    async with built_test_device:
        matched_address_gates = [
            i.Gate for i in await built_test_device.addresses() if match_interface in i.Labels
        ]
        log.info(f"Matched {len(matched_address_gates)} addresses with {match_interface}")
        log.info([i for i in matched_address_gates])

        for gate in matched_address_gates:
            if not gate.FlowID == match_type:
                continue
            matched_gate = gate

        assert matched_gate, "Failed to match an address with the given search params"


async def disconnect_all_device_rx_sords(device):
    async with device:
        await device.addresses.disconnect([sord for sord in device.sords(direction='rx')])


@pytest.fixture(scope='class')
def device(built_test_device):
    # Device for test
    yield built_test_device
    asyncio.run(disconnect_all_device_rx_sords(built_test_device))


@pytest.fixture(scope='class',
                params=[sords_pb2.Essence.VIDEO,
                        sords_pb2.Essence.AUDIO,
                        sords_pb2.Essence.META,
                        sords_pb2.Essence.GPIO],
                ids=lambda param: next(v.name for v in sords_pb2.Essence._enum_type.values if v.number == param)
                )
def essence(request):
    return request.param


@pytest.fixture(scope='function')
def flows(device, essence):
    # Get at least
    # 2 different tx flows of the required type
    # 3 different rx flows of the required type
    tx_flows, rx_flows = [], []
    for direction in ['tx', 'rx']:
        for sord in device.sords(direction=direction):
            for flow in sord.flows:
                if not len(tx_flows) == 2 and direction == 'tx' and flow.essence == essence and flow not in tx_flows:
                    tx_flows.append(flow)
                if not len(rx_flows) == 3 and direction == 'rx' and flow.essence == essence and flow not in rx_flows:
                    rx_flows.append(flow)
    # Check test is valid
    if not len(tx_flows + rx_flows) == 5:
        pytest.skip(f"The device {device.label} does not have enough flows of the required type")
    all_flows = (tx_flows, rx_flows)
    yield all_flows
    asyncio.run(disconnect_all_device_rx_sords(device))


def check_any_sords_can_connect(all_tx_sords, all_rx_sords):
    tx_flow_esseneces = [flow.essence for flow in
                         list(itertools.chain.from_iterable([sord.flows for sord in all_tx_sords]))]
    rx_flow_esseneces = [flow.essence for flow in
                         list(itertools.chain.from_iterable([sord.flows for sord in all_rx_sords]))]
    return len(set(tx_flow_esseneces).intersection(set(rx_flow_esseneces)))


def handle_address_connect_empty(tx_sords, rx_sords, error):
    if check_any_sords_can_connect(tx_sords, rx_sords):
        pytest.fail(
            f"Sords were expected valid for connection but AddressConnectEmptyError was still raised: {str(error)}"
        )
    else:
        pytest.xfail("Expected failure with AddressConnectEmptyError: no given sords are valid for connection")
