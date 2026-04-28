from ldf.models.base import (ClientConfig, HomeNativeDeviceSpec,
                             LawoHomeNativeDevice)


class LawoLcuDevice(LawoHomeNativeDevice):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)
        self.spec = HomeNativeDeviceSpec(
            type_number="850/50",
            model="LCU",
            flags={
                'CreateDeleteSords': True,
                'InternalRouting': True,
                'EditSenders': True,
                'IsPhysical': True,
                'IsStreamer': True
            }
        )
