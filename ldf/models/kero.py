import asyncio
import logging
import time
from typing import Any, Callable

from datamodel.apps import apps_home, apps_pb2
from datamodel.ctls import ctls_home
from datamodel.devices import devices_home, devices_pb2
from datamodel.kero.node import node_pb2
from datamodel.mv import mv_home, mv_pb2
from nats.errors import NoRespondersError

from ldf.attributes.controls import LawoHomeNativeControl, UnknownGCFPageError
from ldf.models.base import (ClientConfig, LawoHomeNativeDevice,
                             subscribe_for_updates)

log = logging.getLogger(__name__)


""" App Server """


class LawoAppServer(LawoHomeNativeDevice):

    node = node_pb2.Node()

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)

    def _updates(self) -> list[tuple[str, Callable]]:
        return [
            (f"kero.update.nodes.{self.id}.change", self.cb_update_node),
            (f"update.endpoints.{self.id}.>", super().cb_update_endpoint)
        ]

    async def cb_update_node(self, subject):
        _, _, _, dev_id, _ = subject.split('.')
        if self.dev_id == dev_id:
            self.node = await self.get_node()

    async def __aenter__(self) -> None:
        await self.client.connect()
        try:
            self.node = await self.get_node()
        except NoRespondersError:
            self.log.debug("Atempted to get Node but failed - Server may be Offline")
        except Exception as e:
            raise e
        await subscribe_for_updates(self.client, self._updates())

    async def __aexit__(self, *args):
        await self.client.nc.flush()
        await self.client.disconnect()

    async def get_node(self):
        """ Used to get the App Server node statically """
        requ = node_pb2.Get()
        resp = node_pb2.GetReply()
        data, err = await self.client.request(
            f"kero.get.nodes.{self.id}", requ, resp)
        return data.Node

    async def reboot(self, timeout=600, wait_for_offline=True, wait_for_online=True):
        """ Will reboot the app server

        Args:
            wait_for_offline (bool, optional): Will block until the server reports it is offline. Defaults to False.
            wait_for_online (bool, optional): Will block until the server reports it is offline. Defaults to True.
            timeout (int, optional): How long to wait for the server to get back online, if  Defaults to 600.

        Raises:
            e: May raise a nats error/timeout error

        Examples:
            reboot(wait_for_offline=True, wait_for_online=True)
                - Will wait for the server to go ffline then block until it's back online
            reboot(wait_for_offline=True, wait_for_online=False)
                - Will wait for the server to go offline but won't wait for it to come back online
            reboot(wait_for_offline=False, wait_for_online=False)
                - Won't wait at all, will only trigger reboot and continue
            reboot(wait_for_offline=False, wait_for_online=True)
                - Invalid case, Will log a warning and simply reboot and not wait
        """
        log.info(
            f"Attempting to reboot App Server {self.label}")
        try:
            await super().reboot()
        except Exception as e:
            log.info(f"Failed rebooting: {self.label}")
            raise e
        if not wait_for_offline and wait_for_online:
            self.log.warning(
                "App server Reboot: Invalid operation - you are waiting for the"
                "server to be online without first waiting for the server to be offline")
            return
        if wait_for_offline:
            await self.wait_for_online_status(False, timeout=30)
        if wait_for_online:
            await self.wait_for_online_status(True, timeout=timeout)

    async def wait_for_online_status(self, online=True, timeout=180):
        """ Waits for the server to be online or offline

        Args:
            state (bool, optional): Defines wethere we should wait
                for the server to be online or offline. Defaults to True.
            timeout (int, optional): How long to wait. Defaults to 180.

        Raises:
            TimeoutError: Raised if the epxected state is not reached in time.
        """
        start_time = time.time()
        expected_state = devices_pb2.AliveState.ONLINE if online else devices_pb2.AliveState.OFFLINE
        log.info(f"Waiting for {self.label} to be {'online' if online else 'offline'}...")
        while True:
            try:
                status, _ = await devices_home.devices_get_one(self.client, self.id)
                if status[0].Alive == expected_state:
                    if online:
                        log.info(f"App server online/ready: {self.label}")
                    else:
                        log.info(f"App server offline: {self.label}")
                    break
                await asyncio.sleep(10)
            except Exception as e:
                log.warning(f"Error checking server {self.label}: {e}")
            if time.time() - start_time > timeout:
                raise TimeoutError(
                    f"{self.label} did was not {'online' if online else 'offline'} within {timeout} seconds.")

    async def set_system(
        self,
        app_deployment: bool = None,
        app_deployment_via_auto: bool = None,
        server_group_for_auto_deployment: str = None,
        stream_redundancy: bool = None,
        st2110_single_srd_mode: bool = None
    ):
        """
        Will set all controls on Advanced > System. Any arguments 'None' wont change the current values

        Args:
            app_deployment (bool, optional): Wethere or not apps deploy. Defaults to None.
            app_deployment_via_auto (bool, optional): The server can deploy apps started with 'Auto'. Defaults to None.
            server_group_for_auto_deployment (str, optional): Group tag for the server. Defaults to None.
            stream_redundancy (bool, optional): Enable or disbale redundancy. Defaults to None.
            st2110_single_srd_mode (bool, optional): Enable or disable SRD mode for 2110 senders. Defaults to None.
        """

        ctls = self.controls.advanced['System'].controls
        ctls_change = [
            (ctls['Enabled'], app_deployment),
            (ctls['EnableAutoTarget'], app_deployment_via_auto),
            (ctls['Group'], server_group_for_auto_deployment),
            (ctls['EnableStreamRedundancy'], stream_redundancy),
            (ctls['EnableSingleSrdMode'], st2110_single_srd_mode),
        ]
        await set_ctls(self, ctls_change)


""" HOME Apps """


class LawoHomeNativeApp(LawoHomeNativeDevice):
    """A base instance for all HOME App types.
    Defines the updates to register for along with appropriate cb functions.

    Args:
        LawoHomeNativeDevice: Inherits from the main HOME native class
    """

    info: apps_pb2.App
    type: str

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)

    def _updates(self) -> list[tuple[str, Callable]]:
        """Override parent class function to extend update subjects to register for
        on connection along with an appropriate callback function to handle the update.

        Returns:
            list[tuple[str, Callable]]: Subject / handler callback pair
        """

        return [
            (f"update.endpoints.{self.id}.>", super().cb_update_endpoint),
            ("update.apps.>", self.cb_update_application),
            ("update.addresses.>", self.cb_update_addresses),
        ]

    async def cb_update_application(self, msg):
        """Handle incoming update messages for HOME Applications"""

        self.log.debug(f"Update received on >> {msg.subject}")
        updated_section = apps_pb2.Update()
        updated_section.MergeFromString(msg.data)
        for app in updated_section.Apps:
            if app.ID == self.guid:
                self.info = app
                break
        self.log.debug(f"Update: {updated_section}")

    async def __aenter__(self) -> None:
        await super().__aenter__()
        # Get info on current state
        app_info_message = await apps_home.apps_get(
            self.client, '', self.guid, '', '', '', 1, '')
        self.info = app_info_message[0][0]

    async def trigger_failover(
            self,
            failover_timeout=30,
    ) -> dict:
        """ Will manually trigger the failover of an App

        Args:
            failover_timeout (int, optional): How long to wait for a failover to occur
            (this should be the general expected start time of an app). Defaults to 30.

        Returns:
            dict: descriptive failover results
        """

        # Failover status to report after failover attempt
        failover_status = {
            'initial server': list,
            'target server': list,
            'final server': list,
        }

        # Failover controls
        # Get the failover mode, target fail over server, holdoff time (will be added to total timeout)
        ctl_mode = self.controls.advanced['Redundancy'].controls['Mode']
        ctl_redundancy_tag = self.controls.advanced['Redundancy'].controls['Group']
        ctl_holdoff = self.controls.advanced['Redundancy'].controls['Holdoff']
        await self.controls.get([ctl_mode, ctl_redundancy_tag, ctl_holdoff])
        mode = ctl_mode.value.value
        redundancy_target = ctl_redundancy_tag.value.value
        holdoff = ctl_holdoff.value.value

        # Initial failover server status
        failover_status['initial server'] = self.info.RunningOnDeviceIDs
        failover_status['target server'] = [redundancy_target]

        # Trigger the failover
        ctl_failover_trigger = self.controls.advanced['Redundancy'].controls['Failover']
        await self.controls.get([ctl_failover_trigger])  # temp fix for events
        await self.controls.set([ctl_failover_trigger])

        # We won't wait for any failover if:
        # 1. Failover is OFF
        # 2. A redundancy group tag is not set
        # 3. The app is already running on it's target failover server
        # 4. The target app server cannot support the app
        if mode == ctl_mode.options['No Failover'] \
            or redundancy_target == '' \
                or self.info.RunningOnDeviceIDs == [redundancy_target] \
                or redundancy_target not in self.info.TargetDeviceIDs:
            msg = (
                "Failover was not triggered because either:\n"
                "1. Failover was OFF\n"
                "2. The redundancy group tag was not set\n"
                "3. The app was already running on it's target failover server")
            log.warning(msg)
            failover_status['final server'] = self.info.RunningOnDeviceIDs
            return failover_status

        # We will wait for the app to failover when:
        # 1. Failover is ON
        # 2. A redundancy group tag is set
        # 3. The app is not running on it's target failover server
        start_time = asyncio.get_running_loop().time()
        while not self.info.RunningOnDeviceIDs == [redundancy_target]:
            if asyncio.get_running_loop().time() - start_time > (failover_timeout + holdoff):
                log.info(
                    f"App: {self.label} stopped but did not start \
                    on target failover server {redundancy_target} when failing over")
                failover_status['final server'] = self.info.RunningOnDeviceIDs
                return failover_status
            await asyncio.sleep(1)
        log.info(f"App: {self.label} successfully failed over onto server: {redundancy_target}")

        # Return failover status
        failover_status['final server'] = self.info.RunningOnDeviceIDs
        return failover_status

    async def update_ctls(self, timeout=10):
        """Wait until GCF controls are populated or raise UnknownGCFPageError."""

        try:
            async with asyncio.timeout(timeout):
                while True:
                    try:
                        ctls, _ = await ctls_home.ctls_get_ctl_all(self.client, self.id)
                        self.ctls = ctls
                        try:
                            sub_pages = self.controls.advanced['Send'].sub_pages
                        except Exception:
                            sub_pages = []
                        if sub_pages:
                            return
                    except UnknownGCFPageError:
                        pass
                    except Exception as e:
                        log.warning(f"Error updating ctls for {self.label}: {e}")
                    await asyncio.sleep(1)
        except asyncio.TimeoutError:
            raise UnknownGCFPageError(
                f"GCF pages for {self.label} did not populate within {timeout} seconds.")


class LawoVirtualMixerApp(LawoHomeNativeApp):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)


class LawoMultiViewerApp(LawoHomeNativeApp):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)

    async def get_pip_config(self, device_id: str) -> tuple[list[mv_pb2.PIPConfig], str]:
        return await mv_home.mv_get_pipc_onfigs(self.client, device_id)

    async def update_pip_config(self, configs: list[mv_pb2.PIPConfig]) -> str:
        return await mv_home.mv_set_sections(self.client, configs)

    async def get_default_bindings(self, widget_id: str, protocol_id: str) -> tuple[mv_pb2.Binding, str]:
        return await mv_home.mv_get_default_binding(self.client, widget_id, protocol_id)


class LawoUDXApp(LawoHomeNativeApp):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)


class LawoColourCorrectorApp(LawoHomeNativeApp):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)


class LawoGraphicInserterApp(LawoHomeNativeApp):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)


class LawoTPGApp(LawoHomeNativeApp):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)


class LawoStreamTranscoderApp(LawoHomeNativeApp):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)


class LawoDSKApp(LawoHomeNativeApp):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)


class LawoTimecodeGeneratorApp(LawoHomeNativeApp):

    def __init__(self, client_cfg: ClientConfig) -> None:
        super().__init__(client_cfg=client_cfg)


""" Helper Functions """


async def set_ctls(device: LawoHomeNativeDevice, ctl_change: list[tuple[LawoHomeNativeControl, Any]]):
    """ Will take a list of controls and values to set useful

    Args:
        device (LawoHomeNativeDevice): Device to set controls on
        ctl_change (list[tuple[LawoHomeNativeControl, Any]]): A list of controls and values to set
    """

    ctl_change = {ctl: value for ctl, value in ctl_change if value is not None}
    await device.controls.get(ctl_change.keys())
    for ctl, value in ctl_change.items():
        ctl.value.value = value
    await device.controls.set(ctl_change.keys())
