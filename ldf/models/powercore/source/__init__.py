from enum import Enum
from typing import cast

from ember_py import EmberClient

from ldf.models.powercore.source.eq import Eq
from ldf.models.powercore.source.limiter import Limiter


class MfKey:
    def __init__(self, client: EmberClient, path: str):
        self._client = client
        self._path = path

    @property
    async def label(self) -> str:
        return cast(str, await self._client.get(f"{self._path}.1.Value"))

    @property
    async def pressed(self) -> bool:
        return cast(bool, await self._client.get(f"{self._path}.2.Value"))

    @property
    async def led(self) -> str:
        color = (await self._client.get(f"{self._path}.3.1")).enum_value
        low = await self._client.get(f"{self._path}.3.2.Value")
        blinking = await self._client.get(f"{self._path}.3.3.Value")

        return ("blinking " if blinking else "") + ("low " if low else "") + color

    async def bang(self) -> None:
        if await self.pressed:
            raise Exception("trying to bang a button that is already in pressed state")

        await self._client.set(f"{self._path}.2", True)
        await self._client.set(f"{self._path}.2", False)


class RumbleValue(Enum):
    Off = 0
    _40Hz = 1
    _80Hz = 2
    _140Hz = 3


class SourceNotFound(Exception):
    def __init__(self, identifier):
        super().__init__(
            f"Source with identifier '{identifier}' cannot be found in the ember tree"
        )


channel_width_lookup = {
    0: 0,
    1: 1,
    2: 2,
    3: 6,
    4: 8,
}


class Source:
    _client: EmberClient
    _identifier: str

    def __init__(self, client: EmberClient, identifier: str):
        self._client = client
        self._path = None
        self._url = None
        self._identifier = identifier

    @property
    async def path(self):
        if self._path is not None:
            return self._path
        for child in (await self._client.get("1.1")).children:
            if child.identifier == self._identifier:
                self._path = child.full_path
                return self._path

        raise SourceNotFound(self._identifier)

    @property
    async def url(self):
        if self._url is not None:
            return self._url

        root = (await self._client.get("/")).url_path

        for child in (await self._client.get(f"{root}/Sources")).children:
            if child.identifier == self._identifier:
                self._url = child.url_path
                return self._url

        raise SourceNotFound(self._identifier)

    async def initialize(self):
        if (await self.get_channel_width()) == 2:
            await self.set_balance(0)
            await self.set_LR_mode("stereo")

        await self.set_channel_on(True)

        await self.get_fresh_eq()
        await self.get_fresh_limiter()

    async def set_balance(self, val):
        return await self._client.set(
            f"{await self.path}.4.1.10",
            val,
            ignore_already_set=True
        )

    async def get_LR_mode(self):
        return await self._client.get(f"{await self.path}.4.1.8")

    async def get_LR_mode_str(self):
        lr_mode = await self.get_LR_mode()

        modes = lr_mode.content("Enumeration").split("\n")
        current_mode = lr_mode.value

        current_mode_str = modes[current_mode]
        return current_mode_str

    async def set_LR_mode(self, mode: str):
        return await self._client.set(
            f"{await self.path}.4.1.8",
            mode,
            ignore_already_set=True
        )

    async def set_channel_on(self, state: bool):
        return await self._client.set(
            f"{await self.path}.4.1.16",
            state,
            ignore_already_set=True
        )

    async def set_phase_flip(self, state: bool):
        return await self._client.set(
            f"{await self.path}.4.1.7",
            state,
            ignore_already_set=True,
        )

    async def get_phase_flip(self):
        return await self._client.get(
            f"{await self.path}.4.1.7"
        )

    async def get_fader_stats(self):
        out = {}
        node = await self._client.get(f"{await self.path}.3")

        for child in node.children:
            value = child.value
            if child.identifier in ("Motor dB Value", "Manual dB Value"):
                """TODO: specify behaviour"""
                continue
                # value = round(value, 12)
            out[child.identifier] = value

        return out

    async def assign_fader(self, target: int):
        return await self._client.set(
            f"{await self.path}.3.1",
            target,
            ignore_already_set=True
        )

    async def set_fader_position(self, value):
        return await self._client.set(
            f"{await self.path}.3.3",
            value,
            ignore_already_set=True,
        )

    async def set_fader_db(self, value):
        return await self._client.set(
            f"{await self.path}.3.2",
            float(value),
            ignore_already_set=True,
        )

    async def get_fresh_eq(self):
        eq = Eq(self._client, await self.url)
        await eq.reset()
        return eq

    async def get_fresh_limiter(self):
        limiter = Limiter(self._client, await self.url)
        await limiter.reset()
        return limiter

    async def get_key(self, identifier):
        key_path = f"{await self.path}.6"

        for child in (await self._client.get(key_path)).children:
            if child.identifier == identifier:
                return MfKey(self._client, child.full_path)

        raise Exception(
            f"could not find MF Key '{identifier}' in source '{self._identifier}'"
        )

    async def get_channel_width(self):
        type_val = await self._client.get(f"{await self.path}.1.Value")

        return channel_width_lookup.get(type_val, 0)

    async def set_digital_gain(self, val: int):
        return await self._client.set(
            f"{await self.path}.4.1.1",
            val,
            ignore_already_set=True
        )

    async def get_digital_gain(self):
        return (await self._client.get(
            f"{await self.path}.4.1.1",
        )).value

    async def set_mic_gain(self, val: int):
        return await self._client.set(
            f"{await self.path}.4.1.2",
            val,
            ignore_already_set=True
        )

    async def get_mic_gain(self):
        return (await self._client.get(
            f"{await self.path}.4.1.2",
        )).value

    async def set_rumble_filter(self, val: RumbleValue | int):
        if type(val) is RumbleValue:
            val = val.value

        return await self._client.set(
            f"{await self.path}.4.1.4",
            cast(int, val),
            ignore_already_set=True
        )

    async def get_rumble_filter(self):
        return (await self._client.get(
            f"{await self.path}.4.1.4",
        )).enum_value

    async def set_pad(self, val: bool):
        return await self._client.set(
            f"{await self.path}.4.1.5",
            val,
            ignore_already_set=True
        )

    async def get_pad(self):
        return (await self._client.get(
            f"{await self.path}.4.1.5",
        )).value

    async def set_phantom_power(self, val: bool):
        return await self._client.set(
            f"{await self.path}.4.1.6",
            val,
            ignore_already_set=True
        )

    async def get_phantom_power(self):
        return (await self._client.get(
            f"{await self.path}.4.1.6",
        )).value
