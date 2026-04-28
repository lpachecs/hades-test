from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Type, TypeVar

from ember_py import CondensedElement, EmberClient, new_connection

from ldf.models.base import ClientConfig, LawoHomeNativeDevice
from ldf.models.powercore.gpios import GPIOs
from ldf.models.powercore.matrix import Matrix
from ldf.models.powercore.on_air_designer import OnAirDesigner
from ldf.models.powercore.serial_connection import SerialConnection
from ldf.models.powercore.sop_explorer import SopExplorer
from ldf.models.powercore.source import Source
from ldf.models.powercore.telnet import Telnet, TelnetConfig

T = TypeVar("T", bound=GPIOs)


class NodeSummary(dict):
    def __init__(self, node: CondensedElement):
        self.identifier = node.identifier
        for c in node.children:
            if c.content("Enumeration") is not None:
                value = c.enum_value
            else:
                value = c.value
            self[c.identifier] = value


class RavennaReceiver(NodeSummary):
    pass


class RavennaSender(NodeSummary):
    pass


class ProjectInfo:
    _node: CondensedElement

    def __init__(self, node: CondensedElement):
        self._node = node

    @property
    def name(self):
        return self._node.walk("/Name")[0].value

    @property
    def version(self):
        return self._node.walk("/Version")[0].value

    @property
    def descriptions(self):
        return (
            self._node.walk("/Description 1")[0].value,
            self._node.walk("/Description 2")[0].value,
            self._node.walk("/Description 3")[0].value,
            self._node.walk("/Description 4")[0].value,
        )


@dataclass(frozen=True)
class PowercoreConfigInfo:
    file: Path
    unit: str | None


class EmberRequiredError(Exception):
    pass


def ensure_ember(fn):

    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        assert getattr(self, "ember") is not None, EmberRequiredError(
            "expecting class to be initiated with an EmBER+ client")

        return fn(self, *args, **kwargs)

    return wrapper


class LawoPowercoreDevice(LawoHomeNativeDevice):
    _config_info: PowercoreConfigInfo | None
    ember: EmberClient

    def __init__(self, client_cfg: ClientConfig, spec=None, ember_client=None):
        self._config_info = None
        super().__init__(client_cfg, spec=spec, ember_client=ember_client)

    def get_config_name(self):
        return self.ember.get("1.29.22.1.Value")

    async def get_sample_rate(self):
        return (await self.ember.get("1.29.2.6")).enum_value

    async def set_96k(self, state):
        return await self.ember.set("1.29.2.5", state, ignore_already_set=True)

    async def get_reference_levels(self):
        """returns `(dBu, dbFS)`"""
        return (
            await self.ember.get("1.29.2.2.Value"),
            await self.ember.get("1.29.2.3.Value")
        )

    async def get_ptp_domain(self):
        root = await self.ember.get("1.6.1")
        if root.identifier != "PTP":
            return None
        return await self.ember.get("1.6.1.1.1.Value")

    async def get_project_info(self):
        info = await self.ember.get("1.29.22")
        return ProjectInfo(info)

    @ensure_ember
    async def get_ravenna_senders(self) -> list[RavennaSender]:
        sender_root = await self.ember.get("/PowerCore/RAVENNA/Core/Inputs")

        return [
            RavennaSender(
                await self.ember.get(x.full_path)
            ) for x in sender_root.children
        ]

    @ensure_ember
    async def get_ravenna_receivers(self) -> list[RavennaReceiver]:
        receiver = await self.ember.get("/PowerCore/RAVENNA/Core/Outputs")

        return [
            RavennaReceiver(
                await self.ember.get(x.full_path)
            ) for x in receiver.children
        ]

    def get_matrix(self):
        return Matrix(self.ember)

    @ensure_ember
    def get_source(self, identifier: str):
        return Source(self.ember, identifier)

    @ensure_ember
    def get_gpios(self, template: Type[T]) -> T:
        """
        usage example:
        ```
        from ldf.models.powercore.gpios import GPIOs


        class TestGPIOs(GPIOs):
            root_name = "TESTCASE.GPIO"

            class Input(Enum):
                Foo = "EGPI.MM.Mono"
                Bar = "EGPI.MM.InDim

        [...]

        gpios = powercore.get_gpios(TestGPIOs)
        await gpios.set_input(gpios.Input.Bar, True)
        ```
        """
        return template(self.ember)

    """SoP Explorer and OnAirDesigner helpers"""

    def ensure_latest_firmware(self):
        sop = SopExplorer(self.ember.host)
        if sop.is_firmware_update_required():
            sop.update_firmware(True)

    async def upload_config(self, path: str | Path, unit: str | None = None, host: str | None = None):
        path = Path(path)
        if not path.exists():
            raise Exception(f"config {path} cannot be found")
        if host is None and self.ember is not None:
            host = self.ember._options.host

        if self.ember is not None:
            await self.ember.close()

        sop = SopExplorer(host)
        oad = OnAirDesigner(host)

        self.log.info("converting config ...")
        if path.suffix == ".db3":
            cfg_path = oad.convert_config(path, unit)
        else:
            cfg_path = path

        self.log.info("... conversion done")

        self.log.info("uploading config ...")

        sop.upload_config(cfg_path)
        self.log.info("... upload done")

        if self.ember is not None:
            self.ember = await new_connection(host, self.ember._options.port, True)

        self._config_info = PowercoreConfigInfo(path, unit)

    @property
    def config_info(self):
        return self._config_info

    def telnet(self, /, user: str | None = None, passwd: str | None = None, credentials_file: Path | None = None):
        if credentials_file is not None:
            try:
                creds_file = credentials_file.resolve()
                with open(creds_file, "r") as tn_creds:
                    c = tn_creds.read().strip()

                    tn_user, tn_pw = c.split(":")[:2]

            except Exception:
                raise Exception(
                    f"expecting telnet credentials 'user:pass' in {creds_file.absolute()}"
                )
        else:
            tn_user = str(user)
            tn_pw = str(passwd)

        if tn_user is None or tn_pw is None:
            raise Exception("need credentials to open telnet connection")

        if self.ember is None:
            raise Exception("cannot connect to telnet. host not provided.")

        return Telnet(TelnetConfig(
            host=self.ember._options.host,
            user=tn_user,
            passwd=tn_pw,
        ))

    def serial_connection(self):
        return SerialConnection()

    @staticmethod
    async def create(ember_host: str, ember_port: int = 9000):
        ember_client = await new_connection(ember_host, ember_port)
        return LawoPowercoreDevice([], ember_client=ember_client)
