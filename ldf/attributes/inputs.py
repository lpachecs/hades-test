import logging

from datamodel.endpoints import endpoints_pb2

from ldf.attributes.controls import (LawoGCFPage, LawoHomeNativeControl,
                                     NoGCFDeviceError)

log = logging.getLogger(__name__)


class LawoHomeNativeInput:
    """A generic class to represent a single physical media input on an endpoint device"""

    def __init__(self, input: endpoints_pb2.InternalTerminal | LawoGCFPage) -> None:
        self.input = input

        # Device is GCF capable
        if isinstance(input, LawoGCFPage):
            self.is_gcf = True
            self.path = input.path
            self.label = input.label

        # Device is not GCF capable
        elif isinstance(input, endpoints_pb2.InternalTerminal):
            self.is_gcf = False
            self.path = input.ID
            self.label = input.Label

    def __repr__(self) -> str:
        return f"{self.label} | {self.path} | {self.controls()}"

    def controls(self) -> list[LawoHomeNativeControl]:
        try:
            return [x for x in self.input.controls.values()]
        except AttributeError:
            return [ctl for ctl in self.input.CtlIDs]


class LawoHomeNativeInputs:
    """A base device class used as an accesor to all physical media inputs on an endpoint device"""

    def __init__(self, device):
        self.device = device

    def __call__(self) -> dict[str, LawoHomeNativeInput]:
        """Generate a dictionary of the devices physical media inputs.

        Attempts to collect inputs using GCF but falls back to InternalTerminals if the device
        does not allow GCF control.

        Returns:
            dict[str, LawoHomeNativeInput]: Dict providing access to controllable Input objects
        """

        try:
            ips = self.device.controls.advanced['SdiInput']
            return {
                label: LawoHomeNativeInput(page) for label, page in ips.children.items()
            }

        except NoGCFDeviceError:                # Device is not GCF capable / Build Inputs using InternalTerminals
            ips = self.device.terminals(
                direction='tx',
                no_ip=True
            )

            # ctls = self.device.controls()
            # return {ctl.path: ctl for ctl in ctls.values()}
            return {
                ip.Label: LawoHomeNativeInput(ip) for ip in ips
            }

    def __getitem__(self, key: str) -> LawoHomeNativeInput | None:
        """Provides access to the Input object using the input label / ID

        Example:
            device.inputs['Mic/Line-1']

            or

            device.inputs['SDI#01']

        Args:
            key (str): A label identifier for the desired input

        Returns:
            LawoHomeNativeInput: A controllable object representing the requested input
        """

        return self().get(key)
