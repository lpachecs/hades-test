import pytest

pytestmark = [pytest.mark.dependency]


class TestCreateAudioSender:

    async def test_create_audio_tx(self, built_test_device):

        async with built_test_device:
            await built_test_device.sords.create(
                count=1,
                flows=["audio"],
                # pri={'mcast_addr': "239.1.1.1", "udp_port": 1234}
            )

    @pytest.mark.parametrize("chans", [2, 4, 6, 8, 16, 32, 64])
    async def test_create_audio_tx_ch_count(self, built_test_device, chans):

        coro = built_test_device.sords.create(
            count=1,
            flows=["audio"],
            ch_count=chans
        )
        async with built_test_device:
            await coro

    @pytest.mark.parametrize("codec", ["L16", "L24", "L32", "AM824"])
    async def test_create_audio_tx_codec(self, built_test_device, codec):

        coro = built_test_device.sords.create(
            count=1,
            flows=["audio"],
            codec=codec
        )
        async with built_test_device:
            await coro

    @pytest.mark.parametrize("frame_size", [2, 4, 6, 12, 16, 24, 32, 48])
    async def test_create_audio_tx_framesize(self, built_test_device, frame_size):

        coro = built_test_device.sords.create(
            count=1,
            flows=["audio"],
            frame_size=frame_size
        )
        async with built_test_device:
            await coro

    async def test_create_audio_tx_tieline(self, built_test_device):

        async with built_test_device:
            await built_test_device.sords.create(
                count=1,
                flows=["audio"],
                is_tieline=True,
            )


class TestCreateAudioReceiver:

    async def test_create_audio_rx(self, built_test_device):

        async with built_test_device:
            await built_test_device.sords.create(
                count=1,
                is_dest=True,
                flows=["audio"],
            )

    async def test_create_audio_rx_tieline(self, built_test_device):

        async with built_test_device:
            await built_test_device.sords.create(
                count=1,
                is_dest=True,
                flows=["audio"],
                is_tieline=True,
            )

    async def test_create_audio_rx_multi_flows(self, built_test_device):

        async with built_test_device:
            await built_test_device.sords.create(
                count=1,
                is_dest=True,
                flows=["audio", "audio", "audio"],
            )
