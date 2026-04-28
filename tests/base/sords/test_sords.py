import asyncio

import pytest
import sdp_transform
from datamodel.sords import sords_pb2

from ldf.models.base import LawoHomeNativeDevice
from tests import log

SORD_UPDATE_TIMEOUT = 1
SORD_RTP_PAYLOAD_MODIFIER = 95
SORD_UDP_PORT_MODIFIER = 8008
SORD_AUDIO_PARAM_MODIFIER = {
    "FrameSize": 48,
    "NumChans": 6,
    "Codec": sords_pb2.AudCodec.AM824,
    "Delay": 69,
    "Syntonized": False,
    "MaxRxChans": 18
}
REQUIRE_SORD_FAIL_MSG = "Failed to find the created test sord on device.\
    This can happen if the device does not return the created sords' data \
    in response to a createSordsRequest or if the device has indeed failed \
    to create the required test sord."

pytestmark = pytest.mark.dependency


@pytest.fixture
async def require_audio_sender(built_test_device: LawoHomeNativeDevice):
    """Create a 2ch audio sender sord on the test device

    Args:
        built_test_device (LawoHomeNativeDevice): Device under test
    """

    async with built_test_device:
        created = await built_test_device.sords.create_audio(
            count=1,
            ch_count=2,
            direction="tx",
            label="LDF_sords_test"
        )

    try:
        yield next((x for x in created))
    except StopIteration:
        pytest.fail(REQUIRE_SORD_FAIL_MSG)
    finally:
        async with built_test_device:
            await built_test_device.sords.remove(created)


@pytest.fixture
async def require_audio_receiver(built_test_device: LawoHomeNativeDevice):
    """Create a 2ch generic audio receiver sord on the test device

    Args:
        built_test_device (LawoHomeNativeDevice): Device under test

    Returns:
        Iterable[sords_pb2.Sord]: Protobuf structure of the created sord
    """

    async with built_test_device:
        created = await built_test_device.sords.create_audio(
            count=1,
            ch_count=2,
            direction="rx",
            label="LDF_sords_test"
        )

    try:
        yield next((x for x in created))
    except StopIteration:
        pytest.fail(REQUIRE_SORD_FAIL_MSG)
    finally:
        async with built_test_device:
            await built_test_device.sords.remove(created)


class TestAudioSender:

    @pytest.mark.parametrize('sord_type', ['audio', 'video', 'meta', 'gpio'])
    def test_get_senders(self, built_test_device, sord_type):
        """Validate audio sender data from the device"""

        log.info(f"Validating {sord_type} sender sords:")
        for sord in built_test_device.sords(
            direction='tx', essence=sord_type
        ):
            log.info(f"\t{sord}")
            assert isinstance(sord.pb, sords_pb2.Sord), \
                f"Expected sords_pb2.Sord, got {type(sord)}"

    async def test_create_audio_sender(self, built_test_device):
        """Validate correct updates are sent by the device when new sender sord is created"""

        async with built_test_device:
            created = await built_test_device.sords.create_audio(
                count=8,
                ch_count=6,
                direction='tx',
                label='LDF_test_sender',
                attrs={'frame_size': 8}
            )

            for sord in created:
                assert sord.ID in [
                    x.ID for x in built_test_device.sords(
                        essence='audio',
                        direction='tx'
                    )
                ]

            log.info(f"Created sord(s): {created}")
            # await built_test_device.sords.remove(created)

    async def test_remove_audio_sender(self, built_test_device, require_audio_sender):
        """Validate removal of audio sender sord and appropriate updates"""

        async with built_test_device:
            await asyncio.sleep(SORD_UPDATE_TIMEOUT)

            log.info(f"Removing audio sender(s): {require_audio_sender}")
            removed_ids = await built_test_device.sords.remove([require_audio_sender])
            await asyncio.sleep(SORD_UPDATE_TIMEOUT)

            try:
                assert require_audio_sender.ID in removed_ids, "Removed sord ID not in 'remove' reply"
                assert require_audio_sender.ID not in [
                    sord.ID for sord in built_test_device.sords(
                        essence='audio',
                        direction='tx'
                    )
                ], "Removed sord was not removed from LDF model endpoint"
            except AssertionError as err:
                log.debug(built_test_device.sords(essence='audio', direction='tx'))
                raise err

    @pytest.mark.parametrize('flow_id', ["audio", "video", "meta"])
    async def test_validate_sender_sdp(self, built_test_device, require_audio_sender, flow_id):
        """Ensure no invalid SDP attributes are presented by sender objects"""

        async with built_test_device:
            sdp = await built_test_device.sords.get_sdp(
                require_audio_sender,
                target_flow=flow_id
            )

        log.info(sdp)
        try:
            sdp_dict = sdp_transform.parse(sdp)
        except UnboundLocalError:
            pytest.xfail(f"No SDP exists for flow: {flow_id}")

        try:
            assert len(sdp_dict['invalid']) == 0, \
                f"Invalid attributes found in SDP ({require_audio_sender.ID}, {require_audio_sender.Label})"
        except KeyError:
            pass

    async def test_set_audio_sender_rtp_payload(self, built_test_device, require_audio_sender):
        """Ensure existing audio sender flow RTP Payload change and appropriate updates"""

        async with built_test_device:

            for flow in require_audio_sender.Flows:
                flow.RtpPayload = SORD_RTP_PAYLOAD_MODIFIER
            log.info(f"Modified sord data: {require_audio_sender}")
            await built_test_device.sords.update([require_audio_sender])
            await asyncio.sleep(SORD_UPDATE_TIMEOUT)

        for sord in built_test_device.sords(essence='audio'):
            if not sord.ID == require_audio_sender.ID:
                continue
            flow_rtp_values = [
                getattr(flow, "RtpPayload") for flow in require_audio_sender.Flows
            ]
            log.info(f"{sord.ID} >> {flow_rtp_values}")

        assert SORD_RTP_PAYLOAD_MODIFIER in flow_rtp_values

    async def test_set_audio_sender_udp_port(self, built_test_device, require_audio_sender):
        """Ensure existing audio sender sord destination UDP port change and appropriate updates"""

        async with built_test_device:
            await asyncio.sleep(SORD_UPDATE_TIMEOUT)

            for flow in require_audio_sender.Flows:
                flow.Pri.DestPort = SORD_UDP_PORT_MODIFIER
                flow.Sec.DestPort = SORD_UDP_PORT_MODIFIER
            log.info(f"Modified sord data: {require_audio_sender}")
            await built_test_device.sords.update([require_audio_sender])
            await asyncio.sleep(SORD_UPDATE_TIMEOUT)

        for sord in built_test_device.sords(essence='audio'):
            if not sord.ID == require_audio_sender.ID:
                continue
            for flow in require_audio_sender.Flows:
                flow_udp_values = (flow.Pri.DestPort, flow.Sec.DestPort)
                log.info(f"{sord.ID} >> {flow_udp_values}")

        assert SORD_UDP_PORT_MODIFIER in flow_udp_values

    @pytest.mark.parametrize('sender_audio_param', ["FrameSize", "NumChans", "Codec"])
    async def test_set_audio_sender_parameters(self, built_test_device, require_audio_sender, sender_audio_param):
        """Ensure existing audio sender flow audio parameter change and appropriate updates"""

        async with built_test_device:
            await asyncio.sleep(SORD_UPDATE_TIMEOUT)

            for flow in require_audio_sender.Flows:
                setattr(
                    flow.AudParams,
                    sender_audio_param,
                    SORD_AUDIO_PARAM_MODIFIER[sender_audio_param]
                )
            log.info(f"Modified sord data: {require_audio_sender}")
            await built_test_device.sords.update([require_audio_sender])
            await asyncio.sleep(SORD_UPDATE_TIMEOUT)

        for sord in built_test_device.sords(essence='audio'):
            if not sord.ID == require_audio_sender.ID:
                continue
            results = [
                getattr(flow.AudParams, sender_audio_param) for flow in sord.Flows
            ]
            log.info(f"{sord.ID} >> {results}")

        assert SORD_AUDIO_PARAM_MODIFIER[sender_audio_param] in results


class TestAudioReceiver:

    @pytest.mark.parametrize('sord_type', ['audio', 'video', 'meta', 'gpio'])
    def test_get_receivers(self, built_test_device, sord_type):
        """Validate audio sender data from the device is the correct data type"""

        log.info(f"Validating {sord_type} receiver sords:")
        for sord in built_test_device.sords(
            direction='rx', essence=sord_type
        ):
            log.info(f"\t{sord}")
            assert isinstance(sord.pb, sords_pb2.Sord), \
                f"Expected sords_pb2.Sord, got {type(sord)}"

    async def test_create_audio_receiver(self, built_test_device):
        """Validate correct updates are sent by the device when a new receiver sord is created"""

        async with built_test_device:
            created = await built_test_device.sords.create_audio(
                count=1,
                ch_count=2,
                direction='rx',
                label='LDF_test_receiver'
            )

            await asyncio.sleep(1)
            for sord in created:
                assert sord.ID in [x.ID for x in built_test_device.sords()]

    async def test_remove_audio_receiver(self, built_test_device, require_audio_receiver):
        """Validate removal of audio sender sord and appropriate updates"""

        async with built_test_device:
            await asyncio.sleep(SORD_UPDATE_TIMEOUT)

            log.info(f"Removing audio receiver(s): {require_audio_receiver.ID}")
            removed_ids = await built_test_device.sords.remove([require_audio_receiver])
            await asyncio.sleep(SORD_UPDATE_TIMEOUT)
            assert require_audio_receiver.ID not in [
                sord.ID for sord in built_test_device.sords(
                    direction='rx',
                    essence='audio'
                )
            ], "Removed sord was not removed from LDF model endpoint"
            assert require_audio_receiver.ID in removed_ids, "Removed sord ID not in 'remove' reply"

    @pytest.mark.parametrize('recv_audio_param', ["Delay", "Syntonized", "MaxRxChans"])
    async def test_set_audio_receiver_parameters(self, built_test_device, require_audio_receiver, recv_audio_param):

        async with built_test_device:
            await asyncio.sleep(SORD_UPDATE_TIMEOUT)

            for flow in require_audio_receiver.Flows:
                setattr(
                    flow.AudParams,
                    recv_audio_param,
                    SORD_AUDIO_PARAM_MODIFIER[recv_audio_param]
                )
            await built_test_device.sords.update([require_audio_receiver])
            log.info(f"Modified sord data: {require_audio_receiver}")
            await asyncio.sleep(SORD_UPDATE_TIMEOUT)

        for sord in built_test_device.sords(essence='audio'):
            if not sord.ID == require_audio_receiver.ID:
                continue
            results = [
                getattr(flow.AudParams, recv_audio_param) for flow in sord.Flows
            ]

        log.info(f"{sord.ID} >> {results}")
        assert SORD_AUDIO_PARAM_MODIFIER[recv_audio_param] in results
