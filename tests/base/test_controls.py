import pytest

from ldf.attributes.controls import (LawoHomeNativeControl,
                                     LawoHomeNativeControlValue)
from tests import log

pytestmark = pytest.mark.dependency


def test_list_all_device_controls(built_test_device):

    for ctl in built_test_device.controls().values():
        log.info(ctl)
        assert isinstance(ctl, LawoHomeNativeControl)
        assert isinstance(ctl.value, LawoHomeNativeControlValue)
