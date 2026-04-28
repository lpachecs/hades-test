import pytest

from ldf.attributes.controls import LawoHomeNativeControl
from ldf.attributes.inputs import LawoHomeNativeInput
from tests import log

pytestmark = pytest.mark.dependency


@pytest.fixture
def mic_gain_ids(built_test_device):
    """A list of all Microphone/Gain control type IDs on the target device"""

    return sorted(
        ctl.path for ctl in built_test_device.controls().values()
        if ctl.label == "MicLine/Microphone/Gain"
    )


@pytest.fixture
def phantom_ids(built_test_device):
    """A list of all Microphone/PhantomPower control type IDs on the target device"""

    return sorted(
        ctl.path for ctl in built_test_device.controls().values()
        if ctl.label == "MicLine/Microphone/PhantomPower"
    )


@pytest.fixture
def pad_ids(built_test_device):
    """A list of all Microphone/Pad control type IDs on the target device"""

    return sorted(
        ctl.path for ctl in built_test_device.controls().values()
        if ctl.label == "MicLine/Microphone/Pad"
    )


@pytest.fixture
def line_mode_ids(built_test_device):
    """A list of all Mic/Line state control type IDs on the target device"""

    return sorted(
        ctl.path for ctl in built_test_device.controls().values()
        if ctl.label == "MicLine/LineMode"
    )


def test_list_device_inputs(built_test_device):
    """List all of the physical media inputs on the target device"""

    for ip in built_test_device.inputs().values():
        log.info(ip)
        assert isinstance(ip, LawoHomeNativeInput)


@pytest.mark.parametrize('input_label', ['Mic/Line-1'])
def test_input_controls(built_test_device, input_label):
    """Validate all device input control object types"""

    device_input = built_test_device.inputs[input_label]
    for ctl_id in device_input.control_ids():
        ctl = built_test_device.controls[ctl_id]
        log.info(ctl)
        assert isinstance(ctl, LawoHomeNativeControl)


@pytest.mark.parametrize('gain_value', [-18.0, 10.0, 25.0])
async def test_set_microphone_gain_single(built_test_device, gain_value, mic_gain_ids):
    """Verify updates when setting the mic gain value of Mic/Line input 1"""

    ctl = built_test_device.controls[mic_gain_ids[0]]
    ctl.value = gain_value

    async with built_test_device:
        await built_test_device.controls.set([ctl])
        assert built_test_device.controls[mic_gain_ids[0]].value.Float == [gain_value], \
            "Control value is not as expected"


@pytest.mark.parametrize('gain_value', [-18.0, 10.0, 25.0])
async def test_set_microphone_gains_all(built_test_device, gain_value, mic_gain_ids):
    """Verify setting all mic gain values + updates on a device"""

    edited_ctls = []
    for ctl_id in mic_gain_ids:
        ctl = built_test_device.controls[ctl_id]
        ctl.value = gain_value
        edited_ctls.append(ctl)

    async with built_test_device:
        await built_test_device.controls.set(edited_ctls)

    for ctl_id in mic_gain_ids:
        assert built_test_device.controls[ctl_id].value.Float == [gain_value], \
            f"Control value {ctl_id} is not as expected"


@pytest.mark.parametrize('phantom_value', [True, False])
async def test_set_microphone_phantom_power_single(built_test_device, phantom_value, phantom_ids):
    """Verify updates when setting the mic phantom power state of Mic/Line input 1"""

    ctl = built_test_device.controls[phantom_ids[0]]
    ctl.value = phantom_value

    async with built_test_device:
        await built_test_device.controls.set([ctl])
        assert built_test_device.controls[phantom_ids[0]].value.Bool == [phantom_value], \
            "Control value is not as expected"


@pytest.mark.parametrize('phantom_value', [True, False])
async def test_set_microphone_phantom_power_all(built_test_device, phantom_value, phantom_ids):
    """Verify updates when setting all mic phantom power states on a device"""

    edited_ctls = []
    for ctl_id in phantom_ids:
        ctl = built_test_device.controls[ctl_id]
        ctl.value = phantom_value
        edited_ctls.append(ctl)

    async with built_test_device:
        await built_test_device.controls.set(edited_ctls)

    for ctl_id in phantom_ids:
        assert built_test_device.controls[ctl_id].value.Bool == [phantom_value], \
            f"Control value {ctl_id} is not as expected"


@pytest.mark.parametrize('pad_value', [True, False])
async def test_set_microphone_pad_single(built_test_device, pad_value, pad_ids):
    """Verify updates when setting the mic pad state of Mic/Line input 1"""

    ctl = built_test_device.controls[pad_ids[0]]
    ctl.value = pad_value

    async with built_test_device:
        await built_test_device.controls.set([ctl])
        assert built_test_device.controls[pad_ids[0]].value.Bool == [pad_value], \
            "Control value is not as expected"


@pytest.mark.parametrize('pad_value', [True, False])
async def test_set_microphone_pad_all(built_test_device, pad_value, pad_ids):
    """Verify updates when setting the mic pad state of all inputs of a device"""

    edited_ids = []
    for ctl_id in pad_ids:
        ctl = built_test_device.controls[ctl_id]
        ctl.value = pad_value
        edited_ids.append(ctl)

    async with built_test_device:
        await built_test_device.controls.set(edited_ids)

    for ctl_id in pad_ids:
        assert built_test_device.controls[ctl_id].value.Bool == [pad_value], \
            f"Control value {ctl_id} is not as expected"


@pytest.mark.parametrize('line_state', [True, False])
async def test_set_microphone_line_state_single(built_test_device, line_state, line_mode_ids):
    """Verify setting the mic / line mode state + updates of Mic/Line input 1"""

    ctl = built_test_device.controls[line_mode_ids[0]]
    ctl.value = line_state

    async with built_test_device:
        await built_test_device.controls.set([ctl])
        assert built_test_device.controls[line_mode_ids[0]].value.Bool == [line_state], \
            "Control value is not as expected"


@pytest.mark.parametrize('line_state', [True, False])
async def test_set_microphone_line_state_all(built_test_device, line_state, line_mode_ids):
    """Verify setting the mic / line mode state + updates of all inputs on a device"""

    edited_ids = []
    for ctl_id in line_mode_ids:
        ctl = built_test_device.controls[ctl_id]
        ctl.value = line_state
        edited_ids.append(ctl)

    async with built_test_device:
        await built_test_device.controls.set(edited_ids)

    for ctl_id in line_mode_ids:
        assert built_test_device.controls[ctl_id].value.Bool == [line_state], \
            f"Control value {ctl_id} is not as expected"


@pytest.mark.skip('Unfinished test')
def test_set_microphone_low_cut_freq_single(built_test_device):
    pass


@pytest.mark.skip('Unfinished test')
def test_set_microphone_low_cut_freq_all(built_test_device):
    pass


@pytest.mark.skip('Unfinished test')
def test_set_line_gain_single(built_test_device):
    pass


@pytest.mark.skip('Unfinished test')
def test_set_line_gain_all(built_test_device):
    pass
