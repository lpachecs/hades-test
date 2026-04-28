from datamodel.ctls.ctls_pb2 import CtlAll

from ldf.models.base import (ClientConfig, HomeNativeDeviceSpec,
                             LawoHomeNativeDevice)


class LawoDotEdgeDevice(LawoHomeNativeDevice):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg)
        self.spec = HomeNativeDeviceSpec(
            type_number="A00/40",
            model=".edge",
            terminals={
                'inputs': {
                    'IP': 6144,
                    'SDI': 384
                },
                'outputs': {
                    'IP': 3072,
                    'SDI': 768
                }
            },
            flags={
                'IsPhysical': True,
                'IsStreamer': True,
                'AdmissionsControl': True,
                'EditSenders': True,
                'InternalRouting': True,
                'GenericControls': True,
                'AudioShuffling': True,
                'HasSDIIO': True,
                'IsProxyStreamer': True
            }
        )

        self.ctls: CtlAll
        self.sdi_config: str | None = None
        self.sdi_input_itr: list | None = None
        self.sdi_output_itr: list | None = None
