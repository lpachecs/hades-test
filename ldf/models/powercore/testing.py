from dataclasses import dataclass
from pathlib import Path

from ember_py import EmberClient
from ember_py.testing import TestConf
from pytest import fixture

from ldf.models.powercore import LawoPowercoreDevice


class PowercoreTestConf(TestConf):
    """
    Add this to `conftest.py` to configure the `powercore` fixture.
    ```
    @fixture
    async def powercore_config() -> PowercoreTestConf:
        return PowercoreTestConf(host="127.0.0.1", port=9000)
    ```
    """
    # super().__init__(host, port, None)


@dataclass(frozen=True)
class PowerCoreConfigUpload:
    file: Path
    unit: str = "unit"
    is_96k_conf: bool = False


@fixture(scope="module")
def powercore_config_upload() -> None | PowerCoreConfigUpload:
    return None


@fixture(scope="module")
def powercore_config() -> PowercoreTestConf:
    return PowercoreTestConf(host="192.168.101.240")


@fixture(scope="module")
async def powercore(
    powercore_config: PowercoreTestConf,
    powercore_config_upload: PowerCoreConfigUpload | None
):
    powercore_device = LawoPowercoreDevice([])

    if powercore_config_upload is not None:

        powercore_device.log.info(f"uploading: {powercore_config_upload.file} (unit={powercore_config_upload.unit})")

        await powercore_device.upload_config(
            powercore_config_upload.file,
            powercore_config_upload.unit,
            powercore_config.host,
        )
    try:
        ember_client = EmberClient(
            powercore_config,
        )
        await ember_client.connect()
        powercore_device.ember = ember_client
    except Exception as error:
        powercore_device.log.warning("failed to connect ember client")
        powercore_device.log.error(error)

    yield powercore_device

    if powercore_device.ember is not None:
        try:
            await powercore_device.ember.close()
        except Exception:
            powercore_device.log.error("failed to tear down ember client")
