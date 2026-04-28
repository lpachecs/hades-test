from ldf.models.base import (ClientConfig, HomeNativeDeviceSpec,
                             LawoHomeNativeDevice)


class LawoLocalIODevice(LawoHomeNativeDevice):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)
        self.spec = HomeNativeDeviceSpec(
            type_number="977/40",
            model="Local I/O",
            terminals={
                'inputs': {
                    'Mic/Line': 16,
                    'AES3': 16,
                    'MADI': 32,
                },
                'outputs': {
                    'Line': 16,
                    'AES3': 16,
                    'MADI': 32,
                    'Headphone': 4,
                    'RTW': 8,
                }
            },
            flags={
                'CreateDeleteSords': True,
                'GPIO': True,
                'FindMe': True,
                'Reboot': True,
                'Upgrade': True,
                'InternalRouting': True,
                'AdmissionsControl': True,
                'EditNetworkConfig': True,
                'EditSenders': True,
                'IsPhysical': True,
                'IsStreamer': True,
            }
        )
