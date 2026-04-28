import asyncio
from enum import Enum

from ember_py import EmberClient, EmberClientOptions

from ldf.models.powercore import LawoPowercoreDevice
from ldf.models.powercore.gpios import GPIOs


class TestGPIOs(GPIOs):
    root_name = "TESTCASE.GPIO"

    class Input(Enum):
        Foo = "EGPI.MM.Mono"
        Bar = "EGPI.MM.InDim"


async def main():
    ember = EmberClient(EmberClientOptions(host="192.168.101.240"))
    await ember.connect()
    powercore = LawoPowercoreDevice([], ember_client=ember)

    print("CONFIG:", await powercore.get_config_name())

    source = powercore.get_source("Test")

    print(await source.path)
    print(await source.get_fader_stats())
    print(await source.get_LR_mode_str())

    print(await (await source.get_fresh_limiter()).on)
    print(await (await source.get_fresh_eq()).on)

    for line in (await powercore.get_matrix().ember_matrix).pretty_connections:
        print(line)

    gpio = powercore.get_gpios(TestGPIOs)
    await gpio.set_input(gpio.Input.Bar, True)


if __name__ == "__main__":
    asyncio.run(main())
