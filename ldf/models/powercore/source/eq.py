from typing import List

from ember_py import EmberClient


class EqBand:
    _eq: EmberClient
    _id: str
    _band_enum: List[str] | None

    def __init__(self, client: EmberClient, root_url: str, id: int | str):
        self._client = client
        self._root_url = root_url
        self._id = str(id)
        self._band_enum = None

    async def reset(self, freq, gain, mode_or_q):
        if self._id in ("Band 1", "Band 5"):
            await self.set_mode(mode_or_q)
        else:
            await self.set_q(mode_or_q)
        await self.set_freq(freq)
        await self.set_gain(gain)

    @property
    async def freq(self):
        return (
            await self._client.get(
                f"{self._root_url}/DSP/Equalizer/{self._id}/Frequency",
            )
        ).enum_value

    async def set_freq(self, freq: int):
        await self._client.set(
            f"{self._root_url}/DSP/Equalizer/{self._id}/Frequency",
            freq,
            ignore_already_set=True,
        )

    @property
    async def gain(self):
        return await self._client.get(
            f"{self._root_url}/DSP/Equalizer/{self._id}/Gain[dB]?Value"
        )

    async def set_gain(self, gain: int):
        """gain: -15 - 15"""
        return await self._client.set(
            f"{self._root_url}/DSP/Equalizer/{self._id}/Gain[dB]",
            gain,
            ignore_already_set=True,
        )

    @property
    async def mode(self):
        return (
            await self._client.get(f"{self._root_url}/DSP/Equalizer/{self._id}/Mode")
        ).enum_value

    async def set_mode(self, mode: str):
        return await self._client.set(
            f"{self._root_url}/DSP/Equalizer/{self._id}/Mode",
            mode,
            ignore_already_set=True,
        )

    @property
    async def q(self):
        return (
            await self._client.get(f"{self._root_url}/DSP/Equalizer/{self._id}/Q")
        ).enum_value

    async def set_q(self, q: str):
        return await self._client.set(
            f"{self._root_url}/DSP/Equalizer/{self._id}/Q",
            q,
            ignore_already_set=True,
        )


class Eq:
    _client: EmberClient

    def __init__(self, client: EmberClient, root_url: str):
        self._client = client
        self._root_url = root_url

    async def reset(self):
        await self.set_on(False)
        await self.get_band(1).reset("180 Hz", 0, "LowShelve")
        await self.get_band(2).reset("494 Hz", 0, "2.0")
        await self.get_band(3).reset("1.61 kHz", 0, "2.0")

        await self.get_band(4).reset("6.27 kHz", 0, "2.0")
        await self.get_band(5).reset("19.9 kHz", 0, "HighShelve")
        return self

    @property
    async def on(self):
        return await self._client.get(f"{self._root_url}/DSP/Equalizer/On?Value")

    async def set_on(self, state: bool):
        return await self._client.set(
            f"{self._root_url}/DSP/Equalizer/On",
            state,
            ignore_already_set=True,
        )

    def get_band(self, num: int):
        """num: 1-5"""

        return EqBand(self._client, self._root_url, f"Band {num}")
