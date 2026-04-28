import pytest

from ldf.attributes.outputs import LawoHomeNativeOutput
from tests import log

pytestmark = pytest.mark.dependency


def test_list_device_inputs(built_test_device):
    """List all of the physical media inputs on the target device"""

    for op in built_test_device.outputs().values():
        log.info(op)
        assert isinstance(op, LawoHomeNativeOutput)
