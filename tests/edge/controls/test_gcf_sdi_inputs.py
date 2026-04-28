import pytest

from ldf.attributes.controls import LawoGCFPage
from tests.edge import display_gcf_page_controls

pytestmark = [
    pytest.mark.dependency
]


def test_ctrls_all_sdi_input(target_device):
    """Test will validate the SDI input controls"""

    input_page = target_device.controls.advanced['SdiInput']
    assert isinstance(input_page, LawoGCFPage)
    display_gcf_page_controls(input_page)


def test_ctrls_single_sdi_input(target_device_input):
    """Test will validate the SDI input controls"""

    assert isinstance(target_device_input, LawoGCFPage)
    display_gcf_page_controls(target_device_input)


def test_ctrls_sdi_input_audio(target_device_input):
    """Test will validate the controls for each Audio page listed in the SDI Inputs Audio page"""

    input_audio_page = target_device_input['Audio']
    assert isinstance(input_audio_page, LawoGCFPage)
    display_gcf_page_controls(input_audio_page)


def test_ctrls_sdi_input_audio_ip_senders(target_device_input):
    """Test will validate the controls for each Audio page listed in the SDI Inputs Audio page"""

    input_audio_senders_page = target_device_input['IpFlow']
    assert isinstance(input_audio_senders_page, LawoGCFPage)
    display_gcf_page_controls(input_audio_senders_page)
