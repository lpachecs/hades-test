import logging

from datamodel.endpoints import endpoints_home, endpoints_pb2


class LawoUhdCoreMixers:

    def __init__(self, device) -> None:
        self.log = logging.getLogger(__name__)
        self.device = device
        self.configs = {}

    def __repr__(self):
        return " | ".join([x for x in self.configs])

    def __iter__(self):
        for mixer in self.configs:
            yield self.configs[mixer]

    def __len__(self):
        return len(self.configs)

    async def set_config(self, modified_config: endpoints_pb2.MixerConfig):
        await endpoints_home.endpoints_set_mixer_config(
            self.device.client,
            self.device.id,
            modified_config
        )
