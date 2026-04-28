from ldf.models.base import (ClientConfig, HomeNativeDeviceSpec,
                             LawoHomeNativeDevice)


class LawoAmicDevice(LawoHomeNativeDevice):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg)
        self.spec = HomeNativeDeviceSpec(
            type_number="985/01",
            model="A__mic8",
            terminals={
                'inputs': {
                    'Mic/Line': 8,
                },
                'outputs': {
                    'Line': 4,
                }
            },
            flags={
                'IsPhysical': True,
                'IsStreamer': True,
                'EditSenders': True,
                'AdmissionsControl': True,
                'EditNetworkConfig': True,
                'GPIO': True,
                'FindMe': True,
                'Reboot': True,
                'Upgrade': True,
                'CreateDeleteSords': True,
                'InternalRouting': True,
                'EditNetworkConfig': True,
                'FindMe': True,
                'Reboot': True,
                'Upgrade': True
            }
        )
