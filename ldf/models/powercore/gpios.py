from asyncio import timeout
from enum import Enum
from logging import getLogger

from ember_py import EmberClient


class MissingRootName(Exception):
    """Thrown when class does not implement root_name.

    example:
    ```
    class Foo(GPIOs):
        # required name:
        root_name = "TEST.GPIO"
    ```
    """

    pass


class GPIOs:
    _client: EmberClient

    _base_path: str
    _filter: str

    root_name: str

    class Input(Enum):
        pass

    class InputLevel(Enum):
        pass

    class Output(Enum):
        pass

    class OutputLevel(Enum):
        pass

    def __init__(self, client: EmberClient):
        self._client = client

        if not hasattr(type(self), "root_name"):
            raise MissingRootName(f"{type(self)}.root_name is not implemented")

        self._base_path = f"/PowerCore/GPIOs/{self.root_name}"
        self.logger = getLogger(type(self).__name__)

    async def get_all_outputs(self):
        """Get states of all GPOs"""
        out = {}

        for gpo in self.Output:
            async with timeout(1):
                value = await self.get_output(gpo)
                out[gpo] = value

        return out

    async def get_all_active_outputs(self):
        all_outs = await self.get_all_outputs()
        out = []

        for key in all_outs:
            if all_outs[key]:
                out.append(key)

        return out

    async def get_output(self, output: Output):
        path = f"{self._base_path}/Output Signals/{output.value}/State?Value"
        value = await self._client.get(path)
        self.logger.info("got {path} {value}")
        return value

    async def set_inputs(self, state: bool):
        """Set all GPIs to state"""
        for gpi in self.Input:
            await self.set_input(gpi, state)

    async def set_input(self, input: Input, state: bool):
        path = f"{self._base_path}/Input Signals/{input.value}/State"
        self.logger.info(f"setting {path}: {state}")
        return await self._client.set(
            path,
            state,
            ignore_already_set=True,
        )

    async def set_input_levels(self, level: int):
        """Set all GPIs to state"""
        for gpi in self.InputLevel:
            await self._client.set(
                f"{self._base_path}/Input Levels/{gpi.value}/Level",
                level,
                ignore_already_set=True,
            )

    async def set_input_level(self, key: InputLevel, level: int):
        await self._client.set(
            f"{self._base_path}/Input Levels/{key.value}/Level",
            level,
            ignore_already_set=True,
        )

    async def trigger_input(self, input: Input):
        await self.set_input(input, True)
        await self.set_input(input, False)
