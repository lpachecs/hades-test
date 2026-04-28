import asyncio
import logging
from typing import Callable, Self

from datamodel.apps import apps_home
from datamodel.client.client import Client as NatsClient
from datamodel.snapshots import snapshots_home
from nats.errors import NoRespondersError

from ldf.attributes.interfaces import create_home_native_interface
from ldf.attributes.sords import LawoHomeNativeSord
from ldf.common.system.addresses import collect_addresses
from ldf.common.system.endpoints import (collect_and_sort_endpoints,
                                         get_endpoint_sections,
                                         get_home_proxy_list)
from ldf.common.system.routing import collect_stitches
from ldf.models.apps_controller import HomeAppsController
from ldf.models.home_controller.authentication import \
    HomeControllerAuthentication
from ldf.models.home_controller.endpoints import HomeControllerEndpoints
from ldf.models.home_controller.routes import HomeControllerRoutes
from ldf.models.home_controller.snapshots import (HomeControllerSnapshot,
                                                  HomeControllerSnapshots)


class HomeControllerConnections:

    def __init__(self, home_addrs: list[str], api_key: str) -> None:
        self.addrs: list[str] = home_addrs
        self.nats: NatsClient = NatsClient(home_addrs, api_key=api_key)
        self.ember: None = None
        self.ssh: None = None
        self.etcd: None = None


class HomeController:
    auth: HomeControllerAuthentication
    endpoints: HomeControllerEndpoints
    apps: HomeAppsController | None
    endpoints: HomeControllerEndpoints
    routes: HomeControllerRoutes
    snapshots: HomeControllerSnapshots

    def __init__(self, conns: HomeControllerConnections) -> None:
        self.log = logging.getLogger("HomeController")
        self.conns = conns
        self._stop_event = asyncio.Event()
        self._c_nats_subs: NatsClient = NatsClient(conns.addrs)
        self._subscription_task: asyncio.Task[None] | None = None

    def _updates(self) -> list[tuple[str, Callable]]:
        """NATs topics to subscribe to on connection w/ callbacks to handle updates

        Returns:
            list[tuple[str, Coroutine]]: Subscription subjects and handler callbacks
        """

        return [
            ("update.devices.>", self.endpoints.cb_device_update),
            ("update.addresses.>", self.routes.cb_update_addrs),
            ("update.snapshots.>", self.snapshots.cb_update_snapshots),
        ] + [
            (f"update.endpoints.{dev.home_id}.sords.>", self.routes.cb_update_sords)
            for dev in self.endpoints.device.values()
        ] + [
            (f"update.sw.{dev.home_id}.stitches.>", self.routes.cb_update_stitches)
            for dev in self.endpoints.switch.values()
        ]

    async def _run_subscriptions(self):
        """Run subscriptions for the lifetime of the object"""

        try:
            async with self._c_nats_subs:
                for sub, cb in self._updates():
                    await self._c_nats_subs.sub(sub, cb)

                self.log.debug("Subscriptions active, waiting for stop event...")
                await self._stop_event.wait()
                self.log.debug("Stop event received")

        except Exception as e:
            self.log.error(f"Subscription error: {e}", exc_info=True)
            if self._c_nats_subs.nc.is_connected:
                await self._c_nats_subs.nc.close()

    @classmethod
    async def create(cls, home_addrs: list[str], api_key: str = "") -> Self:
        """Factory method to create a HomeController instance

        Multiple subscriptions will be created to update the
        HOME controller cache using defined callbacks. This provides
        non-blocking updates to the HOME controller model.

        Args:
            home_addrs (list[str]): List of HOME server IP addresses.

        Returns:
            HomeController: An instance of HomeController.
        """

        obj = cls(HomeControllerConnections(home_addrs, api_key=api_key))
        obj.auth = HomeControllerAuthentication(obj.conns.nats)
        async with obj.conns.nats:

            # Populate the inital endpoints cache (maintained via updates)
            obj.endpoints = HomeControllerEndpoints(
                obj.conns.nats,
                endpoints=await collect_and_sort_endpoints(obj.conns.nats),
                proxies=await get_home_proxy_list(obj.conns.nats, ids="")
            )

            # Get Sords and Interfaces sections for all known endpoints
            # Create LDF Route objects from all Address, Sords and Stiches
            sections = await asyncio.gather(
                *[get_endpoint_sections(obj.conns.nats, ep.home_id)
                  for ep in obj.endpoints]
            )
            obj.routes = HomeControllerRoutes(
                client=obj.conns.nats,
                addrs=[
                    x async for x in collect_addresses(obj.conns.nats)
                ],
                sords=[
                    LawoHomeNativeSord(sord, endpoint.ID)
                    for endpoint in sections if endpoint is not None
                    for sord in endpoint.Sords
                ],
                stitches=[
                    x async for x in collect_stitches(
                        obj.conns.nats,
                        [x.home_id for x in obj.endpoints.switch.values()]
                    )
                ],
                interfaces=[
                    create_home_native_interface(iface)
                    for endpoint in sections if endpoint is not None
                    for iface in endpoint.Interfaces
                ]
            )

            # If HOME Apps install exist on the system, we create a HomeAppsController object
            try:
                app_templates, err = await apps_home.apps_get_templates(obj.conns.nats)
                if not err:
                    obj.apps = HomeAppsController(
                        obj.conns.addrs,
                        app_templates=app_templates
                    )
            except (NoRespondersError, TimeoutError):
                obj.log.debug("Failed to get app.templates. Disabling apps controller")
                obj.apps = None

            # Create the snapshots attribute and populate cache
            snaps, _ = await snapshots_home.snapshots_get(obj.conns.nats, "")
            obj.snapshots = HomeControllerSnapshots(
                obj.conns.nats,
                snaplist=[
                    HomeControllerSnapshot(snap) for snap in snaps
                ]
            )

        # Create a long-running task to manage subscriptions + callbacks
        obj._subscription_task = asyncio.create_task(obj._run_subscriptions())
        obj.log.info(f"Created HOME controller for: {home_addrs}")
        return obj

    async def close(self):
        """Stop subscriptions and clean up NATs connections"""

        if self.endpoints._cache_lock.locked():
            self.log.debug("Waiting for cache lock...")
            try:
                async with asyncio.timeout(3.0):
                    async with self.endpoints_cache_lock:
                        pass  # do nothing until released
            except asyncio.TimeoutError:
                self.log.warning("Cache lock timeout during close")

        self._stop_event.set()
        try:
            await asyncio.wait_for(self._subscription_task, timeout=5.0)
        except asyncio.TimeoutError:
            self.log.warning("Subscription task timeout, cancelling...")
            self._subscription_task.cancel()
            try:
                await self._subscription_task
            except asyncio.CancelledError:
                pass
        self.log.info("HomeController closed")
