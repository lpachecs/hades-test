from datamodel.endpoints import endpoints_pb2
from datamodel.groups import groups_home

from ldf.attributes.mixers import LawoUhdCoreMixers
from ldf.models.base import (ClientConfig, HomeNativeDeviceSpec,
                             LawoHomeNativeDevice)


class LawoGroupableDevice:
    """A mixin class for Lawo devices that are capable of forming redundant groups"""

    async def get_redundancy_group(self) -> endpoints_pb2.RedundancyGroup:
        """Return current information on the containing redundant group

        Returns:
            endpoints_pb2.RedundancyGroup: Group information
        """
        data, err = await groups_home.groups_get_device_group(
            self.client,
            self.id
        )
        return data

    async def join(self, follower):
        group_id, err = await groups_home.groups_join(
            self.client, self.id, follower.id
        )
        if err:
            raise Exception(err)
        return group_id

    async def split(self, group_id, retain_core=""):
        err = await groups_home.groups_split(self.client, group_id, retain_core)
        return err

    async def failover(self):
        err = await groups_home.groups_failover(self.client, self.id)
        return err

    async def get_compatible(self):
        compatibles, err = await groups_home.groups_get_compatible(
            self.client, self.id
        )
        if err:
            self.log.error(err)
        return compatibles


class LawoVirtualMixerSlice(LawoHomeNativeDevice, LawoGroupableDevice):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)
        self.spec = HomeNativeDeviceSpec(
            type_number="720/10",
            model="Virtual Mixer",
            terminals=None,
            flags={
                'IsStreamer': True,
                'IsVirtualSlice': True,
                'IsAudioMixer': True,
                'CreateDeleteSords': True,
                'EditSenders': True,
                'CanBeGrouped': True
            }
        )

    async def get_mixer_config(self) -> endpoints_pb2.MixerConfig:
        return await self.get_sections(["MixerConfig"].MixerConfig)

    def connect_shell(self):
        """Open up an SSH channel to the virtual mixer mcxshell"""
        pass

    def execute_shell_command(self, cmd):
        """Use the SSH channel to the mcxshell to execute command line actions"""
        pass


class LawoUhdCoreDevice(LawoHomeNativeDevice, LawoGroupableDevice):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)
        self.mixers = LawoUhdCoreMixers(self)
        self.spec = HomeNativeDeviceSpec(
            type_number="720/10",
            model="A__UHD Core",
            terminals=None,
            flags={
                'AdmissionsControl': True,
                'CanBeGrouped': True,
                'IsPhysical': True,
                'EditNetworkConfig': True,
                'FindMe': True,
                'IsGroupLeader': True,
                'IsGroupMember': True,
                'Reboot': True,
                  'Upgrade': True,
            }
        )
