from datamodel.sw import sw_home, sw_pb2

# TODO: Add OpenConfig client for each switch device
from ldf.common.gnmi import OpenConfigClient
from ldf.common.system.routing import (HomeControllerStitch,
                                       create_home_controller_stitch)
from ldf.models.base import ClientConfig, LawoHomeNativeDevice


class LawoHomeNetworkSwitch(LawoHomeNativeDevice):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)
        self.gnmi_client: OpenConfigClient | None = None

    async def get_traffic(self, sources: list[str]) -> list[sw_pb2.Traffic]:
        """Get the traffic for the switch.

        Returns:
            list[sw_pb2.Traffic]: The traffic for the switch source.
        """

        self.log.info(f"Getting traffic for switch {sources}")
        traffic_source = sw_pb2.TrafficSource()
        traffic_source.InterfaceIDs.extend(sources)
        self.log.info(traffic_source)

        traffic, err = await sw_home.sw_get_traffic(self.client, self.id, [traffic_source])
        if err:
            self.log.error(f"Failed to get traffic for switch {self.id}: {err}")
            return []
        else:
            return traffic

    async def get_acls(self) -> list[sw_pb2.AccessControlList]:
        """Get the access control lists for the switch.

        Returns:
            list[sw_pb2.AccessControlList]: The access control lists for the switch.
        """

        acls, err = await sw_home.sw_get_acl_s(self.client, self.id)
        if err:
            self.log.error(f"Failed to get ACLs for switch {self.id}: {err}")
            return []
        else:
            return acls

    async def set_acls(self, acls: list[sw_pb2.AccessControlList]) -> None:
        """Set the access control lists for the switch.

        Args:
            acls (list[sw_pb2.AccessControlList]): The access control lists to set for the switch.
        """

        err = await sw_home.sw_set_acl_s(self.client, self.id, acls)
        if err:
            self.log.error(f"Failed to set ACLs for switch {self.id}: {err}")
            raise Exception(err)

    async def remove_acls(self, acls: list[sw_pb2.AccessControlList]) -> None:
        """Remove the access control lists for the switch.

        Args:
            acls (list[sw_pb2.AccessControlList]): The access control lists to remove for the switch.
        """

        err = await sw_home.sw_delete_acl_s(self.client, self.id, acls)
        if err:
            self.log.error(f"Failed to remove ACLs for switch {self.id}: {err}")
            raise Exception(err)

    async def get_stitches(self) -> list[HomeControllerStitch]:
        """Get the stitches for the switch.

        Returns:
            list[sw_pb2.Stitch]: The stitches for the switch.
        """

        stitches, err = await sw_home.sw_get_stitches(self.client, self.id)
        if err:
            self.log.error(f"Failed to get stitches for switch {self.id}: {err}")
            raise Exception(err)
        else:
            return [create_home_controller_stitch(s) for s in stitches]

    async def set_stitches(self, stitches: list[sw_pb2.Stitch]) -> None:
        """Set the stitches for the switch.

        Args:
            stitches (list[sw_pb2.Stitch]): The stitches to set for the switch.
        """

        err = await sw_home.sw_set_stitches(self.client, self.id, stitches)
        if err:
            self.log.error(f"Failed to set stitches for switch {self.id}: {err}")
            raise Exception(err)
