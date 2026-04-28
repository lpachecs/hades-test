from ldf.models.base import ClientConfig, LawoHomeNativeDevice


class LawoAstageDevice(LawoHomeNativeDevice):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg)
