import logging

from datamodel.endpoints import endpoints_pb2

log = logging.getLogger(__name__)


class LawoHomeNativeOutput:
    """A generic class to represent a single physical media output on an endpoint device"""

    def __init__(self, output: endpoints_pb2.InternalTerminal) -> None:
        self.pb = output

        if isinstance(self.pb, endpoints_pb2.InternalTerminal):
            self.path = output.ID
            self.label = output.Label

    def __repr__(self) -> str:
        return f"{self.label} | {self.path} | {self.control_ids()}"

    def control_ids(self) -> list[str]:
        return [x for x in self.pb.CtlIDs]


class LawoHomeNativeOutputs:
    """A base device class used as an accesor to all physical media outputs on an endpoint device"""

    def __init__(self, device) -> None:
        self.device = device

    def __call__(self) -> dict[str, LawoHomeNativeOutput]:
        """Generate a dictionary of the devices physical media outputs.

        Attempts to collect inputs using GCF but falls back to InternalTerminals if the device
        does not allow GCF control.

        Returns:
            dict[str, LawoHomeNativeInput]: Dict providing access to controllable Input objects
        """

        outputs = self.device.terminals(
            direction='rx',
            no_ip=True
        )

        return {
            op.Label: LawoHomeNativeOutput(op) for op in outputs
        }
