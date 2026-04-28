from ember_py import EmberClient


class Limiter:
    def __init__(self, client: EmberClient, root_url: str):
        self._client = client
        self._root_url = root_url

    @property
    async def on(self):
        return await self._client.get(
            f"{self._root_url}/DSP/Limiter/On?Value"
        )

    @property
    async def threshold_db(self):
        return await self._client.get(
            f"{self._root_url}/DSP/Limiter/Threshold[dB]?Value"
        )

    @property
    async def threshold_dbfs(self):
        return await self._client.get(
            f"{self._root_url}/DSP/Limiter/Threshold[dBFS]?Value"
        )

    async def set_active(self, state: bool):
        return await self._client.set(
            f"{self._root_url}/DSP/Limiter/On",
            state,
            ignore_already_set=True,
        )

    async def set_threshold(self, val: int, kind: str = "dB"):
        if kind not in ("dB", "dBFS"):
            raise ValueError(
                f"kind of Limiter threshold should be either 'dB' or 'dBFS'. got '{kind}' instead"
            )

        return await self._client.set(
            f"{self._root_url}/DSP/Limiter/Threshold[{kind}]",
            val,
            ignore_already_set=True,
        )

    async def reset(self):
        await self.set_active(False)
        await self.set_threshold(0)

        assert not await self.on
        assert await self.threshold_db == 0
