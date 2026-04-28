import asyncio
import logging
from typing import Iterable, Self

from datamodel.ctls import ctls_home, ctls_pb2
from datamodel.endpoints import endpoints_home, endpoints_pb2

CTL_TYPE_MAP: dict[str, str] = {
    "bool": "flag",
    "string": "str",
    "largetext": "str",
    "ipv4": "str",
    "float": "flt",
    "number": "num",
    "enum": "num",
    "bitset": "num",
    "event": "flag",
}
log = logging.getLogger(__name__)


class NoGCFDeviceError(Exception):
    """Raised if the device does not have a GCF tree"""
    pass


class UnknownControlError(Exception):
    """Raised if an unknown device control is requested"""
    pass


class UnknownGCFPageError(Exception):
    """Exception raised when the user requests a GCF page that is not associated with this device"""
    pass


class LawoHomeNativeControlValue:
    """An object used to represent the value of a single controllable parameter on an endpoint device.

    The object is able to handle to getting and setting of different types of controls values used by
    HOME native devices.
    """

    def __init__(self, value: ctls_pb2.CtlValue | endpoints_pb2.Value, value_type=None) -> None:
        self.pb = value
        self.value_type = value_type

    def __call__(self) -> float | int | str | bool | None:
        """Return the value of the control as a float, int, str, or bool"""
        return self.value

    @property
    def value(self) -> float | int | str | bool | None:
        """Return the value of the control as a float, int, str, or bool"""

        if isinstance(self.pb, ctls_pb2.CtlValue):
            return getattr(
                self.pb.value,
                CTL_TYPE_MAP.get(self.value_type, ""),
                None
            )

        elif isinstance(self.pb, endpoints_pb2.Value):
            return self.pb
        else:
            return None

    @value.setter
    def value(self, value: float | int | str | bool) -> None:
        """Set the value of the control to a new value

        Args:
            value (float | int | str | bool): The new value to set the control to
        """

        if isinstance(self.pb, ctls_pb2.CtlValue):
            setattr(self.pb.value, CTL_TYPE_MAP.get(self.value_type, ""), value)
        elif isinstance(self.pb, endpoints_pb2.Value):
            # TODO: Implement setting of endpoint values
            self.pb = value


class LawoHomeNativeControl:
    """An object used to represent a single controllable parameter on an endpoint device.

    The object is able to handle to getting and setting of different types of controls values
    including GCF (ctls_pb2.Ctl) and non-GCF (endpoints_pb2.Control) controls. This unification
    provides a single API when scripting or creating tests for endpoint device configuration.
    """

    def __init__(self, control: ctls_pb2.Ctl | endpoints_pb2.Control, parent_id: str | None = None):
        self.pb = control
        self.is_gcf = type(self.pb) is ctls_pb2.Ctl
        self.label = control.ParamID if not self.is_gcf else control.label
        self.parent_id = parent_id

        if isinstance(control, ctls_pb2.Ctl):
            self.ctrl_id = control.id
            self.ctl_type = ctls_pb2.CtlType.keys()[self.pb.ctlType]
            self.iter_scope = control.iterScope.strip("${}") if control.iterScope else None

            # Initial value will be default until calling `control.get()`
            # This allows writing the correct ctl type before the value is known
            # ie. With configuration scripts
            self.value = LawoHomeNativeControlValue(
                ctls_pb2.CtlValue(),
                value_type=self.ctl_type
            )
            self.value.pb.oid = self.path

        elif isinstance(control, endpoints_pb2.Control):
            self.ctrl_id = control.ID
            self.ctl_type = self.pb.Value							 # TODO: Automated type detection
            self.value = LawoHomeNativeControlValue(control.Value)	 # Value is already known
        else:
            self.value = f"Unknown control type: {type(control)}"

    def __str__(self) -> str:
        return f"\t-- {self.ctrl_id:<40} >> {self.path} = {self.value()}"

    @property
    def path(self) -> str | None:
        if not self.is_gcf:
            return self.pb.ParamID
        elif self.is_gcf and self.iter_scope:
            return ".".join([self.parent_id, '#GLOB', self.ctrl_id])
        elif self.is_gcf and not self.iter_scope:
            return ".".join([self.parent_id, self.ctrl_id])

        return None

    @property
    def options(self) -> dict[str, int] | None:
        """Return the options available for an enum control"""

        return {opt: idx for idx, opt in enumerate(self.pb.options)} \
            if hasattr(self.pb, 'options') \
            else None


class LawoGCFPage:

    def __init__(
        self,
        page: ctls_pb2.Page,
        parent: Self | None = None,
        iteration_id: tuple[str, str] | None = None
    ) -> None:

        self.pb: ctls_pb2.Page = page
        self.parent: Self | None = parent
        self.label: str = page.label
        self.children: dict[str, Self] = {}
        self.controls: dict[str, LawoHomeNativeControl] = {}

        self.is_iterator: bool = bool(page.iter) if not iteration_id else False
        self.is_iteration: bool = iteration_id is not None
        self.iter: str = page.id.split("$")[0].strip("{}")
        self.iter_ids: list[str] = [f"#{x}" for x in page.iterDesc.strip('{}').split(',')]
        self.iter_labels: list[str] = page.iterDescLabel.strip('{}').split(',')
        self.iter_ignore: list[str] = page.iterIgnore
        self.ctrl_scope: str | None = "$" + page.id.split("$")[1] if "$" in page.id else None

        # Build the page ID based on the iteration state and parent page ID (if applicable)
        self.id: list = [page.id]
        if self.is_iteration:
            self.id = [iteration_id[0]]
            self.label = f"{page.label} > {iteration_id[1]}"
        if self.is_iterator:
            self.id = [self.iter]
        if parent:
            self.id = parent.path.split('.') + self.id

        if self.is_iterator:
            # Add any GLOB controls to this parent page
            self.controls = {
                ctl.id: LawoHomeNativeControl(ctl, parent_id=self.path)
                for ctl in page.ctls if self.ctrl_scope == ctl.iterScope
            }

            # Add child pages and controls based on iterScope
            for iter_id, iter_label in zip(self.iter_ids, self.iter_labels):
                if iter_id.strip('#') not in [x for x in self.pb.iterIgnore]:
                    self.children[iter_id.strip('#')] = LawoGCFPage(
                        self.pb,
                        parent=self,
                        iteration_id=(iter_id, iter_label)
                    )

                for ctl in page.ctls:
                    if iter_id.strip('#') not in [x for x in ctl.iterIgnore] and self.ctrl_scope != ctl.iterScope:
                        self.children[iter_id.strip('#')].controls[ctl.id] = LawoHomeNativeControl(
                            ctl,
                            parent_id=f"{self.path}.{iter_id}"
                        )

        elif not self.is_iterator:
            # Add controls to page based on scope
            for ctl in self.pb.ctls:
                # TODO: logic reads as "if not in" but should be "if in", why does this work?
                if self.is_iteration and iteration_id[0].strip('#') not in [x for x in ctl.iterIgnore]:
                    continue
                self.controls[ctl.id] = LawoHomeNativeControl(ctl, parent_id=self.path)

            # Add child pages to this page based on scope
            for sub_page in self.pb.pages:
                if self.is_iteration and iteration_id[0].strip('#') in [x for x in sub_page.iterIgnore]:
                    continue
                self.children[sub_page.id.split('$')[0]] = LawoGCFPage(sub_page, parent=self)

    def __repr__(self) -> str:
        """Return a string representation of the GCF page object"""
        return f"{self.label} [{len(self.controls)} Ctrls {len(self.children)} Children] ({self.path})"

    def __iter__(self):
        """Iterate through the sub page labels + page objects of the GCF page

        Returns:
            tuple[str, LawoGCFPage]: The label and page of each child page
        """

        for label, page in self.children.items():
            yield label, page

    def __getitem__(self, itm: str) -> Self:
        """Provides access to any sub pages object using the child page label

        Args:
            itm (str): The ID of the requested control

        Returns:
            LawoGCFPage: The page object for the requested sub page
        """

        try:
            return self.children[itm]
        except KeyError:
            raise UnknownGCFPageError(
                f"Failed to find requested sub page in {self.label}: {itm} ({[x for x in self.children]})"
            )

    @property
    def path(self) -> str:
        """Return the full path of the page including any parent pages"""

        try:
            return ".".join(self.id)
        except TypeError:
            return f"Invalid path: {self.path}"

    @property
    def sub_pages(self) -> list[str]:
        """Return all sub page labels as list"""
        return [x for x in self.children.keys()]

    def is_parent(self) -> bool:
        """Check if the page has any sub pages"""
        return len(self.children) > 0


class LawoGCFAdvancedControls:
    """Provides access to all advanced controls on an capable endpoint device"""

    def __init__(self, ctls_all: ctls_pb2.CtlAll) -> None:
        self.ctls_all = ctls_all

    def __iter__(self):
        """Iterate through the GCF pages on the device

        Returns:
            LawoGCFPage: A controllable class for the requested page
        """

        for page in self.ctls_all.pages:
            yield LawoGCFPage(page)

    def __getitem__(self, itm: str) -> LawoGCFPage:
        """Provides access to the device advanced controls using page ids

        Example:
            device.controls.advanced['SdiInput']
            device.controls.advanced['Synchronization']['Ptp']

        Args:
            itm (str): ID of the GCF Page being accessed

        Returns:
            LawoGCFPage: A controllable class for the requested page
        """

        pages = {x.id.split('$')[0]: x for x in self.ctls_all.pages}
        try:
            return LawoGCFPage(pages[itm])
        except KeyError:
            raise UnknownGCFPageError(
                f"The requested page ({itm}) is not part of this devices GCF definition ->\
                    {[x for x in pages]}"
            )


class LawoHomeNativeControls:
    """A base device class used as an accesor to all (non-GCF) controllable
    parameters on an endpoint device. Care is taken to ensure controls data
    is accessed from the updated device endpoint.
    """

    def __init__(self, device) -> None:
        self.device = device

    def __call__(self) -> dict[str, LawoHomeNativeControl]:
        """Generate a dictionary of the devices controllable parameters

        Returns:
            dict[str, LawoHomeNativeControl]: Dict providing access to Control objects
        """

        return {
            x.ID: LawoHomeNativeControl(x) for x in self.device.endpoint.Controls
        }

    def __getitem__(self, itm: str) -> LawoHomeNativeControl | None:
        """Provides access to a Control object using the control ID.

        Args:
            itm (str): The ID of a requested device control

        Returns:
            LawoHomeNativeControl: Controllable object for the requested control
        """

        try:
            return self().get(itm)
        except KeyError:
            raise UnknownControlError(
                f"Failed to find requested control on {self.device.label}: {itm}"
            )

    @property
    def advanced(self) -> LawoGCFAdvancedControls:
        try:
            return LawoGCFAdvancedControls(self.device.ctls)
        except AttributeError:
            raise NoGCFDeviceError(f"Device {self.device.label} is not GCF capable.")

    async def _request_values_endpoint(self, ctrls: list[LawoHomeNativeControl]) -> list[LawoHomeNativeControl]:
        """Request values for multiple endpoint control parameters and update the control objects

        Args:
            ctrls (list[LawoHomeNativeControl]): A list of Control objects to update
        """

        if not len(ctrls):
            return ctrls

        values, _ = await endpoints_home.endpoints_get_controls(
            self.device.client,
            self.device.id,
            [ctrl.path for ctrl in ctrls]
        )

        for ctl, val in zip(ctrls, values):
            if not ctl.path == val.ID:
                continue
            ctl.value = LawoHomeNativeControlValue(val)

        return ctrls

    async def _request_values_gcf(self, ctrls: list[LawoHomeNativeControl]) -> list[LawoHomeNativeControl]:
        """Request values for multiple GCF control parameters and update the control objects

        Args:
            ctrls (list[LawoHomeNativeControl]): A list of Control objects to update
        """

        if not len(ctrls):
            return ctrls
        values, _ = await ctls_home.ctls_get_ctl_values(
            self.device.client,
            self.device.id,
            [ctrl.path for ctrl in ctrls]
        )

        for val in values:
            ctl = next(
                (x for x in ctrls if x.path == val.oid)
            )
            ctl.value = LawoHomeNativeControlValue(
                val,
                value_type=ctl.ctl_type
            )

        return ctrls

    async def get(self, ctrls: list[LawoHomeNativeControl]) -> list[LawoHomeNativeControl]:
        """Request the current value of multiple control parameters. The method will
        return a list of Control objects with updated values.

        Args:
            ctrls (list[LawoHomeNativeControl]): A list of Control objects to request values for

        Returns:
            list[LawoHomeNativeControl]: A list of Control objects with updated values
        """

        gcf_controls = [x for x in ctrls if x.is_gcf]
        endpoint_controls = [x for x in ctrls if not x.is_gcf]
        await self._request_values_gcf(gcf_controls)
        await self._request_values_endpoint(endpoint_controls)
        return gcf_controls + endpoint_controls

    async def set(self, ctrls: list[LawoHomeNativeControl]) -> None:
        """Send a request to set multiple control parameters to a specified value

        Args:
            ctrls (list[LawoHomeNativeControl]):  A list of modified Control values to apply to the device
        """

        gcf_controls = [x for x in ctrls if x.is_gcf]
        endpoint_controls = [x for x in ctrls if not x.is_gcf]

        if len(gcf_controls):
            try:
                await ctls_home.ctls_set_ctl_values(
                    self.device.client,
                    self.device.id,
                    [x.value.pb for x in gcf_controls]
                )
            except AttributeError as err:
                log.error(f"Failed to set GCF controls: {[x.path for x in gcf_controls]} - {err}")

        if len(endpoint_controls):
            await endpoints_home.endpoints_set_controls(
                self.device.client,
                self.device.id,
                [x.pb for x in ctrls]
            )

        # TODO: block until update message received
        await asyncio.sleep(.2)

    async def get_oids(self, oids: list[str]) -> Iterable[ctls_pb2.Ctl]:
        """Request data using oid values (GCF)

        Args:
            oids (list[str]): List of oids for requested data

        Returns:
            Iterable[ctls_pb2.Ctl]: Protobuf stuctures containing the requested data (if applicaable)
        """

        resp, _ = await ctls_home.ctls_get_ctls(
            self.device.client,
            self.device.id,
            oids
        )
        return resp
