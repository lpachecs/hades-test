import asyncio
import json
import random
import re
from typing import Callable, Coroutine, Dict, Iterable

from datamodel.apps import apps_home, apps_pb2
from datamodel.client.client import Client
from datamodel.devices import devices_home, devices_pb2
from datamodel.licensing import licensing_home
from datamodel.sords.sords_pb2 import Encap, Essence
from nats.aio.msg import Msg

from ldf import log
from ldf.attributes.sords import LawoHomeNativeSord
from ldf.models.base import subscribe_for_updates
from ldf.models.kero import (LawoAppServer, LawoHomeNativeApp,
                             LawoStreamTranscoderApp, LawoTPGApp)

""" Errors/Exceptions """


class UnknownAppError(Exception):
    """ Exception raised when an unknown HOME App name or ID is given """

    def __init__(self, info: str) -> None:
        message = f"Could not find app on system: {info}"
        super().__init__(message)


""" Data classes """


class NetworkOperationsData:
    """ Will be used by HAC to control certain network operations
    This object should (optionally) be passed to HAC """

    def __init__(self, request_wait=0.1):
        """ Set variables
        Args:
            request_wait (int, optional): How many seconds to wait
                between sending requests from HAC. Defaults to 0. """

        self.request_wait = request_wait


class LifecycleTimeouts:
    """ Will be used by HAC set times for lifecycle operations
    This object should (optionally) be passed to HAC """

    def __init__(self, create=2, start=5, healthy=15, stop=2, delete=2):
        """ Set variables
        Args:
            create/start/healthy/stop/delete (int, optional):
                How many seconds to wait for a particular lifecycle request to resolve.
                Defaults based on sensible estimates. """

        self.create = create
        self.start = start
        self.healthy = healthy
        self.stop = stop
        self.delete = delete


""" App data classes """


class AppData:

    def __init__(self, client, info: apps_pb2.App):
        self.client = client
        self.info = info
        self.type = info.Template.ID

    @property
    def label(self) -> str:
        return self.info.Name

    @property
    def guid(self) -> str:
        return self.info.ID

    @property
    def id(self) -> str:
        return self.info.AssociatedDeviceID

    @property
    def template(self) -> apps_pb2.Template:
        return self.info.Template

    @property
    def license_mode(self) -> apps_pb2.LicenseMode:
        return self.info.LicenseMode

    @property
    def license_features(self) -> list[str]:
        return self.info.LicenseFeatures

    @property
    def configuration(self) -> dict:
        return json.loads(self.info.Configuration)

    @property
    def state(self) -> apps_pb2.State:
        state = self.info.State
        return {0: 'stopped', 1: 'running'}.get(state)

    @property
    def health(self) -> apps_pb2.Health:
        return self.info.Health

    @property
    def is_healthy(self) -> bool:
        return self.health == apps_pb2.Health.HEALTH_OK

    @property
    def running_on_device_ids(self) -> list[str]:
        return self.info.RunningOnDeviceIDs

    @property
    def running_on_device_id(self) -> str:
        return self.running_on_device_ids[0] if self.running_on_device_ids else None

    @property
    def device(self) -> LawoHomeNativeApp:
        log.debug(f"Getting LDF App device: {self.label}")
        if not hasattr(self, '_device'):
            self._device = get_home_app_device(self.client, self.guid, self.type)
        log.debug(f"Returning {self.type} '{self.label}'")
        return self._device

    def __repr__(self):
        return f"AppData: {self.label} ({self.type}): "\
               f"{next(k for (k, v) in apps_pb2.State.items() if self.state == v)}"


""" HOME Apps Controller """


class HomeAppsController:

    def __init__(
        self,
        client_addrs: list,
        lifecycle_timeouts=LifecycleTimeouts(),
        net_data=NetworkOperationsData(),
        app_templates=None,
        tracked_names: None | list[str] = None
    ) -> None:
        # client
        self.client = Client(client_addrs)
        # will keep track of all apps
        self.data: Dict[str, AppData] = {}
        # App templates
        if not app_templates:
            app_templates = asyncio.run(get_app_templates(self.client))
        # Organise the app templates
        self.templates = {template.ID: template for template in app_templates}
        # logger
        self.log = log
        # Useful info
        self.info = info
        # Lifecycle timeouts
        self.lifecycle_timeouts = lifecycle_timeouts
        # Network operations data
        self.net_data = net_data
        # HAC will only track apps with given names (can be RegEx)
        self.tracked_names = tracked_names

    async def __aenter__(self) -> None:
        """ On connection HAC gets all current system App Data """

        await self.client.connect()
        log.debug('HAC __aenter__: Getting all apps info from HOME')
        # Update data dict with all apps on system
        if self.tracked_names:
            all_apps_info = []
            for name_pattern in self.tracked_names:
                all_apps_info.extend(await self.get_all_apps_info(name_pattern=name_pattern))
        else:
            all_apps_info = await self.get_all_apps_info()
        log.debug('HAC __aenter__: Populate HAC AppData')
        for app_info in all_apps_info:
            app_name = app_info.Name
            if app_name not in self.data:
                self.data[app_name] = AppData(self.client, app_info)
            else:
                self.data[app_name].info = app_info
        log.debug('HAC __aenter__: Completed HAC AppData update')
        await subscribe_for_updates(self.client, self._updates())

    async def __aexit__(self, *args) -> None:
        await self.client.nc.flush()
        await self.client.disconnect()

    """ Updates """

    def _updates(self) -> list[tuple[str, Callable]]:
        """ Override parent class function to extend update subjects to register for
        on connection along with an appropriate callback function to handle the update.

        Returns:
            list[tuple[str, Callable]]: Subject / handler callback pair """

        return [
            ("update.apps.>", self.cb_update_application),
            ("update.appspartial.>", self.cb_update_application),
        ]

    async def update_apps(self, subject, apps: list[apps_pb2.App]) -> None:
        """ Updates the HAC App data dictionary """

        _, _, _, oper = subject.split('.')
        for app_info in apps:
            app_name = app_info.Name
            if oper == 'insert':
                if self.tracked_names:
                    if not any(re.match(p, app_name) for p in self.tracked_names):
                        continue
                self.data[app_name] = AppData(self.client, app_info)
            elif app_name in self.data:
                if oper == 'change':
                    if "update.apps." in subject:
                        self.data[app_name].info = app_info
                    elif "update.appspartial." in subject:
                        self.data[app_name].info = await self.get_app_info(app_name=app_name)
                elif oper == 'remove':
                    del self.data[app_name]

    async def cb_update_application(self, msg: Msg) -> None:
        """ Handle incoming update messages for HOME Applications """

        self.log.debug(f"Update received on >> {msg.subject}")
        app_update = apps_pb2.Update()
        app_update.MergeFromString(msg.data)
        await self.update_apps(msg.subject, app_update.Apps)

    """ Properties """

    @property
    def default_app_configs(self) -> dict[str: dict]:
        """ Will return a dict of default app configs for each app type """

        all_app_confs = {}
        for app_type, _ in self.templates.items():
            all_app_confs.update({
                f"QAA-DEFAULT-{app_type}".upper():
                    (app_type, self.generate_app_config(app_type))})
        return all_app_confs

    """ LDF device """

    def get_app_dev_by_name(self, app_name: str) -> LawoHomeNativeApp:
        """ Will get an app as a ldf device via its name/label """
        app_data = self.data[app_name]
        app_guid, app_type = app_data.guid, app_data.type
        return get_home_app_device(self.client, app_guid, app_type)

    async def get_app_devices(self, app_names: Iterable[str]) -> list[LawoHomeNativeApp]:
        return [await self.get_app_dev_by_name(name) for name in app_names]

    async def get_system_app_servers(self, running_only=False) -> list[LawoAppServer]:
        """ Get all App Server devices on the system """

        from ldf.production import create_home_native

        device_status, _ = await devices_home.devices_get_all(self.client)
        server_status = [a for a in device_status if a.Model == 'App Server']
        if running_only:
            server_status = [
                s for s in server_status
                if s.Alive == devices_pb2.AliveState.ONLINE]
        guids = [s.GUID for s in server_status]
        return [await create_home_native(
            lawo_type='App Server',
            guid=guid,
            client_addrs=self.client.addrs
        ) for guid in guids]

    """ System-wide NATs requests and async conditions """

    async def get_all_apps_info(self, batch_size=50, name_pattern='') -> list[apps_pb2.App]:
        """ Will get the app info of all home apps from the client """

        log.debug("Getting get.apps() info from HOME")
        start_after = "none"
        all_apps = []
        while start_after != "":
            reply = await apps_home.apps_get(
                self.client,
                argTplID='',
                argAppID='',
                argName=name_pattern,
                argAssociatedDeviceID='',
                argLocation='',
                argLimit=batch_size,
                argStartAfter=start_after
            )
            all_apps += reply[0]
            start_after = reply[2]
        return all_apps

    async def get_app_info(
        self,
        tpl_id="",
        app_guid="",
        app_name="",
        server_guid="",
        location="",
        limit=1,
        start_after_guid=""
    ) -> apps_pb2.App:
        """ Will get app info messages matching any argument provided """

        log.debug(f"Getting get.apps() info of '{app_name}' from HOME")
        try:
            app_info = await apps_home.apps_get(
                client=self.client,
                argTplID=tpl_id,
                argAppID=app_guid,
                argName=app_name,
                argAssociatedDeviceID=server_guid,
                argLocation=location,
                argLimit=limit,
                argStartAfter=start_after_guid
            )
            return app_info[0][0]
        except IndexError:
            raise UnknownAppError(app_name)
        except Exception as e:
            raise e

    async def get_apps_targets(self, app_names: list[str], include_no_go_servers: bool = True) -> dict:
        """ Will get valid App Server targets for a list of apps """

        log.info("Getting App target servers")
        app_guids = [app_data.guid for app_data in self.data.values() if app_data.label in app_names]
        reply, _ = await apps_home.apps_get_targets(self.client, app_guids, include_no_go_servers)

        # Return a sorted dictionary of Targets Data
        targets = {
            'targets': {},
            'valid': [],
            'invalid': []
        }
        for target in reply:
            targets['targets'].update({
                target.ID: {
                    'id': target.ID,
                    'label': target.Label,
                    'invalid': target.Invalid,
                    'no cpu': target.NoCpu,
                    'no memory': target.NoMem,
                    'no io': target.NoIo,
                    'no gpu': target.NoGpu,
                    'disabled': target.Disabled,
                }})
            if not target.Invalid:
                targets['valid'].append(target.ID)
            else:
                targets['invalid'].append(target.ID)
        return targets

    async def check_apps_target_valid(self, app_names: list, server_id: str) -> bool:
        """ Boolean check to verify if a set of apps can start on a server """
        targets = await self.get_apps_targets(app_names)
        return server_id in targets['valid']

    """ App Configuration Generation """

    def generate_app_config(
            self,
            app_type: str,
            custom={},
            force_correct=True,
            rand=False
    ) -> dict:
        """ Will generate a valid HOME App configuration

        Args:
            app_type (str): Type of app defined in app template ID ('udx', 'mv', etc.)
            custom (dict, optional): User defined app configurations by {Key: Value}
                - Any required options for an app will be given defaults if not provided
                - E.G. if you give configs for an MV but don't provide a scan rate 50Hz will be used
            force_correct (bool, optional): Will raise an error if you provide invalid option for the given App
                - E.G. You gave invalid key or value and error will be raised
                - If set to false instead it will just remove the invalid keys
                - Defaults to True
            rand (bool, optional): Will randomize undefined configs instead of using defaults.
                - Defaults to False.

        Raises:
            UnknownAppError: Raised if the given app type is not known
            AssertionError: Raised if you give invalid configuration keys or values

        Returns:
            dict: Dictionary of the app configs
                  Can be passed to HomeAppsController.create_app
        """

        # Get the configuration rules for the app type
        try:
            app_rules = self.templates[app_type].Options
            app_rules = json.loads(app_rules)['properties']
        except KeyError:
            raise UnknownAppError(
                f"Unknown app type '{app_type}'\n"
                f"expected one of: [{list(self.templates.keys())}]"
            )

        # Create the app config
        configs = dict()

        # Raise an error if given App configs are invalid
        invalid_keys = [key for key in custom if key not in app_rules]
        if force_correct and invalid_keys:
            raise AssertionError(
                f"Configuration for app {app_type} was given "
                f"invalid configuration options: {invalid_keys}",
                f"Expected one of: {list(app_rules)}")
        elif invalid_keys:
            log.warning(
                f"Unexpected configuration was given in config generator {invalid_keys}. "
                f"For app {app_type}, these will be removed from the App configuration.")
            [custom.pop(key, None) for key in invalid_keys]

        # Build a valid app configuration with the provided user configs
        for name, prop in app_rules.items():
            # Get all the options for the current setting
            options = prop.get('options', [])
            # If there is not a list of given options for the setting...
            if not options:
                # ... Get from user if provided
                if name in custom:
                    required_type = {
                        'string': str,
                        'number': int,
                        'boolean': bool
                    }.get(prop['type'])
                    assert isinstance(custom[name], required_type), \
                        f"Invalid setting for '{name}': {custom[name]}" \
                        f" - Wrong type was given, expected: {required_type}"
                    configs[name] = custom[name]
                # ... Or select the default
                elif prop.get('default') is not None:
                    configs[name] = prop['default']
                # Move onto the next setting
                continue
            # Only get valid options based on our configuration so far
            valid_options = []
            for opt in options:
                condition = opt.get('when')
                if condition:
                    dependency, allowed_values = condition.split('=')
                    allowed_values = allowed_values.split('|')
                    if configs.get(dependency) and configs.get(dependency) not in allowed_values:
                        continue
                valid_options.append(opt)
            options = [opt['value'] for opt in valid_options]
            # If a desried setting option is set in custom...
            if name in custom:
                # ... Ensure that option is valid or fail
                assert custom[name] in options, \
                    f"Invalid setting for '{name}': {custom[name]}\n" \
                    f"Custom config given: {custom}"
                configs[name] = custom[name]
            else:
                # Always use default values if possible...
                if not rand and app_rules[name].get('default') in options:
                    configs[name] = app_rules[name].get('default')
                # ... Else choose the first valid option or randomize
                elif rand:
                    configs[name] = random.choice(options)
                else:
                    configs[name] = options[0]
        # Return the complete configuration
        return configs

    """ HOME Apps Lifecycle functions """

    async def create_app(
        self,
        app_name: str,
        app_type: str,
        app_configs: dict,
        timeout: int | None = 'auto',
        blocking: bool = True,
        parent_id: str = '',
        add_config_defaults: bool = True
    ) -> AppData:
        """ Will Create a HOME App on the HOME system

        Args:
            app_type (str): The App type as found in apps_pb2.Templates ('mv', 'udx', ...)
            app_name (str): A unique label for the app
            app_configs (dict): App configuration, any missing options will be filled out by default.
            timeout (int | None, optional): How long to wait in seconds. Defaults to 'auto'.
            blocking (bool, optional): If True raises an error on any failure. Defaults to True.
            parent_id (str, optional): Optional parent ID for a synergy child app. Defaults to ''.

        Returns:
            AppData: App Data given after the operation completes
        """

        log.info(f"Creating new {app_type} app: {app_name}")

        # Auto fill missing config options with defaults
        if add_config_defaults:
            app_configs = self.generate_app_config(app_type, custom=app_configs)

        # Create app on system
        await apps_home.apps_create(
            self.client,
            app_type,
            app_name,
            json.dumps(app_configs),
            parent_id
        )

        # Wait for App to register in HOME/HAC data
        await self.wait_for_condition(
            condition=lambda: app_name in self.data,
            timeout=self.lifecycle_timeouts.create if timeout == 'auto' else timeout,
            blocking=blocking,
            timeout_error_message=f"Failed to register App {app_name} on register on HOME"
        )

        # Wait for App to be assined a device ID
        await self.wait_for_condition(
            condition=lambda: self.data[app_name].id != '',
            timeout=self.lifecycle_timeouts.create if timeout == 'auto' else timeout,
            blocking=blocking,
            timeout_error_message=f"Failed to assign ID to App {app_name}",
        )

        return self.data.get(app_name, AppData)

    async def edit_app(
        self,
        app_name: str,
        app_configs: dict,
        license_mode: int = apps_pb2.LicenseMode.AUTO,
        role: str = '',
        target_group: str = '',
        timeout: int | None = 'auto',
        blocking=True
    ) -> AppData:
        """ Will Edit a HOME App on the HOME system (The App must be stopped)

        Args:
            app_name (str): The unique label of the app
            app_configs (dict): New App configuration to Edit to, any missing options will be filled out by default.
            license_mode (int): License mode - see apps_pb2.LicenseMode. Defaults to apps_pb2.LicenseMode.AUTO (0).
            role (str): Option role string (cosmetic). Defaults to ''.
            target_group (str): Target group for 'Auto' app server selection, if not set the previous server is retained
            timeout (int | None, optional): How long to wait in seconds. Defaults to 'auto'.
            blocking (bool, optional): If True raises an error on any failure. Defaults to True.

        Returns:
            AppData: App Data given after the operation completes
        """

        log.info(f"Editing app: {app_name}")
        app_data = self.data[app_name]

        # Auto fill defaults for any missing App configs
        app_configs = self.generate_app_config(app_data.type, custom=app_configs)

        # Send App edit request
        role_obj = apps_pb2.OptionalString()
        role_obj.Value = role
        target_group_obj = apps_pb2.OptionalString()
        target_group_obj.Value = target_group
        await apps_home.apps_edit(
            client=self.client,
            argtplID=app_data.id,
            argappID=app_data.guid,
            argConfiguration=json.dumps(app_configs),
            argLicenseMode=license_mode,
            argRole=role_obj,
            argTargetGroup=target_group_obj
        )

        # Wait for App edit to complete in HOME/HAC data
        await self.wait_for_condition(
            condition=lambda: self.data[app_name].configuration == app_configs,
            timeout=self.lifecycle_timeouts.create if timeout == 'auto' else timeout,
            blocking=blocking,
            timeout_error_message=f"Failed to edit App {app_name}",
        )

        return self.data.get(app_name)

    async def delete_app(
        self,
        app_name: str,
        timeout: int | None = 'auto',
        blocking=True,
        force_stop=True
    ) -> AppData:
        """ Will Delete and Purge a HOME App from the HOME system

        Args:
            app_name (str): The unique label of the app
            timeout (int | None, optional): How long to wait in seconds. Defaults to 'auto'.
            blocking (bool, optional): If True raises an error on any failure. Defaults to True.
            force_stop (bool): Will stop a running app before deleting. Defaults to True.

        Returns:
            AppData: App Data given after the operation completes
        """

        log.info(f"Deleting app: {app_name}")
        app_data = self.data[app_name]

        # Stop App first if required
        if force_stop:
            await self.stop_app(app_name)
            log.info(f"Deleted app: {app_name}")

        # Delete and Purge App from the system
        await apps_home.apps_delete(
            client=self.client,
            argtplID=app_data.type,
            argappID=app_data.guid
        )
        await devices_home.devices_purge_one(
            self.client,
            app_data.id
        )

        # Wait for  App to unregister in HOME/HAC data
        await self.wait_for_condition(
            condition=lambda: app_name not in self.data,
            timeout=self.lifecycle_timeouts.delete if timeout == 'auto' else timeout,
            blocking=blocking,
            timeout_error_message=f"Failed to stop App {app_name}",
        )

        return self.data.get(app_name, AppData)

    async def start_app(
        self,
        app_name: str,
        target_app_server: str | LawoAppServer,
        version: str,
        timeout_start: int | None = 'auto',
        timeout_health: int | None = 'auto',
        blocking: bool = True,
    ) -> AppData:
        """ Will Start a HOME App on an App Server

        Args:
            app_name (str): The unique label of the app
            target_app_server (LawoAppServer | str): Target Server. Can use ID/GUID/'Auto' or LawoAppServer LDF device.
            version (str): Home Apps version to run
            timeout_start (int | None, optional): Timeout in seconds for the App start. Defaults to 'auto'.
            timeout_health (int | None, optional): Timeout in seconds for the App report healthy . Defaults to 'auto'.
            blocking (bool, optional): If True raises an error on any failure. Defaults to True.

        Raises:
            AssertionError: Raised if an app is unlicensed and blocking=True

        Returns:
            AppData: App Data given after the operation completes
        """

        # Get target server ID
        server_id = await get_target_app_server_id(self.client, target_app_server)
        log.info(f"Starting App: {app_name}\nTarget server: {server_id}\nVersion:{version}")
        app_data = self.data[app_name]

        # Check if the app license is valid
        log.info(f"Checking license for App {app_name} valid")
        license_mode = {
            apps_pb2.LicenseMode.AUTO: (False, True, True),
            apps_pb2.LicenseMode.PERPETUAL: (False, False, False),
            apps_pb2.LicenseMode.FLEX: (False, True, False)
        }.get(app_data.license_mode)
        licensing_info = await licensing_home.licensing_get_info(
            self.client, app_data.license_features, app_data.id, *license_mode)
        _, floating_reqs, perpetual_reqs, flex_reqs, _ = licensing_info
        requirements = [*floating_reqs, *perpetual_reqs, *flex_reqs]

        # If the licensing requirement is not valid ...
        if not all(req.Okay for req in requirements):
            unlicensed_message = (
                f"App {app_name} does not have enough licenses to start: "
                f"{[(req.Code, req.Okay) for req in requirements]} ")
            # ... Raise an error if blocking
            if blocking:
                raise AssertionError(
                    f"Cannot start app because it is unlicensed: {app_name}", unlicensed_message)
            # ... Otherwise continue with start request but don't expect the app to start
            unlicensed_message += "- The start request will be sent but the app should stay stopped"
            log.warning(unlicensed_message)

        # Wait for target server to appear in available app targets
        await self.wait_for_condition(
            condition=lambda: self.check_apps_target_valid([app_name], server_id),
            timeout=2,
            blocking=blocking,
            timeout_error_message=f"Failed target validation for App {app_name} on server {server_id}"
        )

        # Start the app
        log.info(f"Starting app: {app_name}")
        await apps_home.apps_start(
            client=self.client,
            argtplID=app_data.type,
            argappID=app_data.guid,
            argTargetID=server_id,
            argVersion=version
        )

        # Wait for the App to register on the server
        def start_condition():
            running = self.data[app_name].running_on_device_id
            return (running == server_id if server_id.lower() != 'auto' else running is not None)
        await self.wait_for_condition(
            condition=start_condition,
            timeout=self.lifecycle_timeouts.start if timeout_start == 'auto' else timeout_start,
            blocking=blocking,
            timeout_error_message=f"Failed to start App {app_name} on target server {server_id}"
        )
        if blocking and server_id.lower() == 'auto':
            server_id = self.data[app_name].running_on_device_id

        # Wait for the App to report itself as Healthy
        await self.wait_for_condition(
            condition=lambda: self.data[app_name].health == apps_pb2.HEALTH_OK,
            timeout=self.lifecycle_timeouts.healthy if timeout_health == 'auto' else timeout_health,
            blocking=blocking,
            timeout_error_message=f"Failed health check on App {app_name} running on {server_id}"
        )

        return self.data.get(app_name)

    async def stop_app(
        self,
        app_name: str,
        timeout: int = 'auto',
        blocking: bool = True
    ) -> AppData:
        """ Will Stop a HOME App on the HOME system

        Args:
            app_name (str): The unique label of the app
            timeout (int | None, optional): How long to wait in seconds. Defaults to 'auto'.
            blocking (bool, optional): If True raises an error on any failure. Defaults to True.

        Returns:
            AppData: App Data given after the operation completes
        """

        log.info(f"Stopping App: {app_name}")
        app_data = self.data[app_name]

        # Send the Stop request
        await apps_home.apps_stop(
            self.client,
            app_data.type,
            app_data.guid
        )

        # Wait for the app to stop on HOME
        await self.wait_for_condition(
            condition=lambda: self.data[app_name].running_on_device_id is None,
            timeout=self.lifecycle_timeouts.stop if timeout == 'auto' else timeout,
            blocking=blocking,
            timeout_error_message=f"Failed to stop app {app_name}"
        )

        return self.data[app_name]

    async def create_apps(
        self,
        app_configurations: dict[str: (str, dict)],
        timeout: int | None = 'auto',
        blocking=True,
        parent_id: str = ''
    ) -> list[AppData]:
        """ Will create many apps on the system at once with asyncio.gather using HAC.create_app

        Args:
            app_configurations (dict): Dictionary containing {app_name: (type, configuration)}
            timeout (int | None, optional): How long to wait in seconds for each individual App. Defaults to 'auto'.
            blocking (bool, optional): Will raise an error if any app fails. Defaults to True.
            parent_id (str, optional): See HAC.create App. Only use if all apps are synergy children. Defaults to ''.

        Returns:
            list[AppData]: App Data given after the operation completes for every App

        Examples:
            await HAC.create_apps(
                {'QAA-MV': ('mv', {'pips': 9})}, {'QAA-UDX': ('udx', {'scanRate': '59.94'})}, timeout=2)
        """

        log.info(f"Creating apps: {list(app_configurations.keys())}")
        assert len(app_configurations) != 0, "App configurations empty"
        tasks = [
            self.create_app(
                app_name=app_name,
                app_type=conf[0],
                app_configs=conf[1],
                timeout=timeout,
                blocking=blocking,
                parent_id=parent_id
            )
            for app_name, conf in app_configurations.items()
        ]
        return await asyncio.gather(*tasks)

    async def edit_apps(
        self,
        app_configurations: dict[str: dict],
        license_mode: int = apps_pb2.LicenseMode.AUTO,
        role: str = '',
        target_group: str = '',
        timeout: int | None = 'auto',
        blocking=True
    ) -> list[AppData]:
        """ Will edit many apps on the system at once with asyncio.gather using HAC.edit_app

        Args:
            app_configurations (dict): Dictionary containing {app_name: (type, configuration)}
            license_mode (int): Sets license mode for all Apps. Defaults to apps_pb2.LicenseMode.AUTO (0).
            role (str): Option role string (cosmetic). Defaults to ''.
            target_group (str): Target group for 'Auto' app server selection, if not set the previous server is retained
            timeout (int | None, optional): How long to wait in seconds for each individual App. Defaults to 'auto'.
            blocking (bool, optional): Will raise an error if any app fails. Defaults to True.

        Returns:
            list[AppData]: App Data given after the operation completes for every App

        Examples:
            await HAC.edit_apps({'QAA-MV': {'pips': 12}, {'QAA-UDX': {'scanRate': '60'}, ...})
        """

        log.info(f"Editing apps: {list(app_configurations.keys())}")
        assert len(app_configurations) != 0, "App configurations empty"
        tasks = [
            self.edit_app(
                app_name=app_name,
                app_configs=conf,
                license_mode=license_mode,
                role=role,
                target_group=target_group,
                timeout=timeout,
                blocking=blocking
            )
            for app_name, conf in app_configurations.items()
        ]
        return await asyncio.gather(*tasks)

    async def delete_apps(
        self,
        app_names: Iterable[str],
        timeout: int | None = 'auto',
        blocking=True,
        force_stop=True
    ) -> list[AppData]:
        """ Will delete many apps on the system at once with asyncio.gather using HAC.delete_app

        Args:
            app_names (list[str]): Every App to delete by name.
            timeout (int | None, optional): How long to wait in seconds for each individual App. Defaults to 'auto'.
            blocking (bool): Will raise an error if any app fails. Defaults to True.

        Returns:
            list[AppData]: A list of all App data after operation complete

        Examples:
            async with HAC:
                await HAC.delete_apps(['QAA-MV', 'QAA-UDX'], 2, True, True)
        """

        app_names = list(app_names)
        log.info(f"Deleting apps: {app_names}")
        assert len(app_names) != 0, "App names empty"
        tasks = [
            self.delete_app(
                app_name=app_name,
                timeout=timeout,
                blocking=blocking,
                force_stop=force_stop
            )
            for app_name in app_names
        ]
        return await asyncio.gather(*tasks)

    async def start_apps(
        self,
        app_names: Iterable[str],
        target_app_server: LawoAppServer | str | None,
        version: str,
        timeout_start: int | None = 'auto',
        timeout_health: int | None = 'auto',
        blocking: bool = True,
    ) -> list[AppData]:
        """ Will start many apps on the system at once with asyncio.gather using HAC.start_app

        Args:
            app_name (str): Every App to start by name.
            target_app_server (LawoAppServer | str): Target Server. Can use ID/GUID/'Auto' or LawoAppServer LDF device.
            version (str): Home Apps version to run for all apps.
            timeout_start (int | None, optional): Seconds to wait for all Apps to start. Defaults to 'auto'.
            timeout_health (int | None, optional): Seconds to wait for all Apps to report healthy. Defaults to 'auto'.
            blocking (bool, optional): If True raises an error on any App failure. Defaults to True.

        Returns:
            list[AppData]: A list of all App data after operation complete

        Examples:
            async with HAC:
                await HAC.start_apps(['QAA-MV', 'QAA-UDX'], 'V9LMHS0XoO1wxofwvXn1wv', 'v1.12.0', 5, 10, True)
        """

        app_names = app_names
        log.info(f"Starting apps: {app_names}")
        assert len(app_names) != 0, "App names empty"
        tasks = [
            self.start_app(
                app_name=app_name,
                target_app_server=target_app_server,
                version=version,
                timeout_start=timeout_start,
                timeout_health=timeout_health,
                blocking=blocking
            )
            for app_name in app_names
        ]
        return await asyncio.gather(*tasks)

    async def stop_apps(
        self,
        app_names: Iterable[str],
        timeout: int | None = 'auto',
        blocking=True
    ) -> list[AppData]:
        """ Will stop many apps on the system at once with asyncio.gather using HAC.stop_app

        Args:
            app_name (str): Every App to stop by name.
            version (str): Home Apps version to run for all apps.
            timeout_start (int | None, optional): Seconds to wait for all Apps to stop. Defualts to 'auto'.
            blocking (bool, optional): If True raises an error on any App failure. Defaults to True.

        Returns:
            list[AppData]: A list of all App data after operation complete

        Examples:
            async with HAC:
                await HAC.stop_apps(['QAA-MV', 'QAA-UDX'], 'auto', True)
        """

        app_names = list(app_names)
        log.info(f"Stopping apps: {app_names}")
        assert len(app_names) != 0, "App names empty"
        tasks = [
            self.stop_app(
                app_name=app_name,
                timeout=timeout,
                blocking=blocking
            )
            for app_name in app_names
        ]
        return await asyncio.gather(*tasks)

    async def wait_for_condition(
        self,
        condition: Callable | Coroutine,
        timeout: int,
        blocking: bool,
        timeout_error_message: str
    ):
        """ Used by HAC to check for certain conditions

        Args:
            condition (Callable): A function call to check for True
            timeout (int): How long to wait
            blocking (bool): Wether or not to raise a TimeoutError or warning
            timeout_error_message (str): Message logged on error
            warning_error_message (str): Message logged on warning

        Raises:
            TimeoutError: Raised when blocking is True and timeout time runs out
        """
        loop = asyncio.get_running_loop()
        start = loop.time()
        timeout_error_message += f"\nOperation failed in: {timeout} seconds"

        while True:
            result = condition()
            if asyncio.iscoroutine(result):
                result = await result
            if result:
                return
            if loop.time() - start >= timeout:
                if blocking:
                    raise TimeoutError(timeout_error_message)
                else:
                    log.warning(timeout_error_message)
                    return
            await asyncio.sleep(0.5)

    # FIXME: Shouldn't define empty sets / dicts in method signature:
    # https://docs.python.org/3/tutorial/controlflow.html#default-argument-values
    async def create_tpg_for_destination_sord(
            self,
            tpg_label: str,
            target_app_server: LawoAppServer | str | None,
            version: str,
            dest_sord: LawoHomeNativeSord,
            custom={},
            rand=False
    ) -> LawoTPGApp:
        """  Will create a TPG suitable for the required video and audio addresses of the receiver

        Args:
            tpg_label (str): TPG label/name
            target_app_server (LawoAppServer): App server to start on, one of LDF device/GUID/'Auto'
            version (str): HOME Apps version to use
            dest_sord (LawoHomeNativeSord): Sord that will be used to configure the valid TPG
            custom (dict, optional): A custom dictionary, the user can set other TPG settings

        Returns:
            LawoTPGApp: LDF device of the TPG
        """

        self.log.info("Attempting to create a TPG for the target destination sord/receiver")

        # Get the required flows from the destination Sord (get the first flow of audio and video)
        video_flow = next((flow for flow in dest_sord.pb.Flows if flow.Essence == Essence.VIDEO), None)
        audio_flow = next((flow for flow in dest_sord.pb.Flows if flow.Essence == Essence.AUDIO), None)

        if not video_flow and not audio_flow:
            log.info("Attempted to create a TPG but no video and audio flow was given")
            return None

        # Select a suitable video transport for the receiver
        if not custom.get('outputVideoTransport'):
            encap = video_flow.Encap if video_flow else audio_flow.Encap
            options = {
                Encap.SMPTE2110_20: ['2110'],
                Encap.JPEG_XS: ['2110-22'],
                Encap.NDI: ['ndi', 'ndi-264', 'ndi-265'],
                Encap.SRT: ['srt-264', 'srt-265'],
                Encap.SMPTE2110_30: ['2110'],
            }.get(encap)
            custom['outputVideoTransport'] = options[0] if not rand else random.choice(options)
        # Always use the highest supported resolution supported by the target receiver
        if not custom.get('outputVideoResolution'):
            caps = [cap for cap in video_flow.Caps if 'JPEG' not in cap][-1] if video_flow else None
            confs = {
                'SD': ['sd'],
                'HD': ['720p', '1080i'],
                '3G': ['1080p'],
                'UHD': ['uhd'],
            }.get(caps, ['1080p'])
            resolutions = json.loads(
                self.templates['tpg'].Options)['properties']['outputResolution']
            options = [
                opt['value'] for opt in resolutions['options']
                if not opt.get('when') or custom['outputVideoTransport'] in opt['when'].split('=')[-1].split('|')
            ]
            custom['outputResolution'] = next(
                (conf for conf in confs[::-1] if conf in options)) if not rand else random.choice(options)
        # Audio configs must match the video transport
        if not custom.get('outputAudioTransport'):
            encap = audio_flow.Encap if audio_flow else video_flow.Encap
            options = {
                Encap.SMPTE2110_30: ['2110'],
                Encap.NDI: ['ndi'],
                Encap.SRT: ['srt'],
                Encap.SMPTE2110_20: ['2110', '2110x2', '2110x4'],
                Encap.JPEG_XS: ['2110', '2110x2', '2110x4'],
            }.get(encap)
            custom['outputAudioTransport'] = options[0] if not rand else random.choice(options)
        # Scan rate must match receiver
        if not custom.get('outputScanRate'):
            scan_rate = video_flow.VidParams.ExactFrameRate
            option = {
                '50': '50',
                '59.94': '59',
                '60': '60',
            }.get(scan_rate)
            custom['outputScanRate'] = option

        # Get the TPG app configs
        configs = self.generate_app_config('tpg', custom=custom, rand=rand)

        # Create and start the TPG
        self.log.info("Adding the TPG to HOME")
        await self.create_app(tpg_label, 'tpg', configs)
        self.log.info("Attempting to start the TPG")
        await self.start_app(tpg_label, target_app_server, version)

        # Return the LDF Device
        return await self.get_app_dev_by_name(tpg_label)

    async def create_stc_for_source_sord(
            self,
            stc_label: str,
            target_app_server: LawoAppServer | str | None,
            version: str,
            source_sord: LawoHomeNativeSord,
            custom={},
            rand=False
    ) -> LawoStreamTranscoderApp:
        """  Will create a STC suitable for the required video and audio addresses of the sender

        Args:
            stc_label (str): STC label/name
            target_app_server (LawoAppServer): App server to start on, one of LDF device/GUID/'Auto'
            version (str): HOME Apps version to use
            source_sord (LawoHomeNativeSord): Sord that will be used to configure the valid STC
            custom (dict, optional): A custom dictionary, the user should can set the desired STC output transport here

        Returns:
            LawoStreamTranscoderApp: LDF device of the STC
        """

        self.log.info("Attempting to create a STC for the target source sord/sender")

        # Get the required flows from the source Sord (Get the first flow of audio and video)
        video_flow = next((flow for flow in source_sord.pb.Flows if flow.Essence == Essence.VIDEO), None)
        audio_flow = next((flow for flow in source_sord.pb.Flows if flow.Essence == Essence.AUDIO), None)

        if not video_flow and not audio_flow:
            log.info("Attempted to create a STC but no video and audio flow was given")
            return None

        # Set input video transport
        if not custom.get('inputVideoTransport'):
            encap = video_flow.Encap if video_flow else audio_flow.Encap
            custom['inputVideoTransport'] = {
                Encap.SMPTE2110_20: '2110',
                Encap.JPEG_XS: '2110-22',
                Encap.NDI: 'ndi',
                Encap.SRT: 'srt',
                Encap.SMPTE2110_30: '2110',
            }.get(encap)
        # Set input resolution
        if not custom.get('inputResolution'):
            caps = video_flow.Caps[0] if video_flow else None
            custom['inputResolution'] = {
                'SD': 'hd',
                'HD': 'hd',
                '3G': '1080p',
                'UHD': 'uhd',
            }.get(caps, 'hd')
        # Set input audio transport
        if not custom.get('inputAudioTransport'):
            encap = audio_flow.Encap if audio_flow else video_flow.Encap
            options = {
                Encap.SMPTE2110_30: ['2110', '2110x2', '2110x4'],
                Encap.NDI: ['ndi'],
                Encap.SRT: ['srt'],
                Encap.SMPTE2110_20: ['2110', '2110x2', '2110x4'],
                Encap.JPEG_XS: ['2110', '2110x2', '2110x4'],
            }.get(encap)
            custom['inputAudioTransport'] = options[0] if not rand else random.choice(options)

        # Get the remaining STC app configs
        configs = self.generate_app_config('transcoder', custom=custom, rand=rand)

        # Create and start the STC
        self.log.info("Adding the STC to HOME")
        await self.create_app(stc_label, 'transcoder', configs)
        self.log.info("Attempting to start the STC")
        await self.start_app(stc_label, target_app_server, version)

        # Return the LDF Device
        return await self.get_app_dev_by_name(stc_label)


async def get_home_app_device(client: Client, app_guid: str, app_type: str):

    from ldf.production import create_home_native

    lawo_app_type = {
        "mv": "Multiviewer App",
        "udx": "UDX App",
        "vmixer": "mc² DSP App",
        "inserter": "Graphic Inserter App",
        "tpg": "Test Pattern Generator App",
        "transcoder": "Stream Transcoder App",
        "dsk": "DSK App",
        "colour": "Color Corrector App",
        "timecode": "Timecode Generator App",
        "delay": "Delay Inserter App",
        "powercore": "Power Core DSP App",
        "audioshuffler": "Audio Shuffler"
    }.get(app_type, app_type)
    app_device = await create_home_native(
        lawo_type=lawo_app_type,
        guid=app_guid,
        client_addrs=client.addrs
    )
    return app_device


async def get_app_templates(client) -> list[apps_pb2.Template]:
    """ Will get the app templates for all available apps on HOME
    which describe applications, their default values, and how they can be configured

    Returns:
        list[apps_pb2.Template]: the templates retrieved
    """

    log.debug("Getting App Templates from HOME")
    async with client:
        templates, _ = await apps_home.apps_get_templates(client)
    return templates


async def get_target_app_server_id(client, identifier: LawoAppServer | str | None):
    """ takes some ideintifier to get an app server's ID """
    if identifier and str(identifier).lower() != 'auto':
        # Get ID from LDF device
        if type(identifier) is LawoAppServer:
            server_id = identifier.id
        # Get ID from guidstr
        elif type(identifier) is str:
            if '-' in identifier:
                server_id = \
                    (await devices_home.devices_allocate(client, identifier))[1]
            # If given server is not a LDF device or guid, assume it's the ID
            else:
                server_id = identifier
        return server_id
    else:
        return 'Auto'


""" Common information for use in HAC """


info = {
    'server':
        {
            'input_costs':
                {
                    'hd': 1,
                    '1080p': 2,
                    'uhd': 8
                },
            'output_costs':
                {
                    'sd': 1,
                    '720p': 1,
                    '1080i': 1,
                    '1080p': 2,
                    'uhd': 8,
                }
        }
}
