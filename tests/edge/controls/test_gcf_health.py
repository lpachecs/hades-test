import pytest

from ldf.attributes.controls import LawoGCFPage
from tests.edge import display_gcf_page_controls

pytestmark = [
    pytest.mark.dependency
]


def test_ctrls_health(target_device):

    health_psu_page = target_device.controls.advanced['Health']
    assert isinstance(health_psu_page, LawoGCFPage)
    display_gcf_page_controls(health_psu_page)


def test_ctrls_health_all_psu(target_device):

    health_psu_page = target_device.controls.advanced['Health']['Psu']
    assert isinstance(health_psu_page, LawoGCFPage)
    display_gcf_page_controls(health_psu_page)


def test_ctrls_health_single_psu(target_device):

    health_psu_page = target_device.controls.advanced['Health']['Psu']['psu0']
    assert isinstance(health_psu_page, LawoGCFPage)
    display_gcf_page_controls(health_psu_page)


def test_ctrls_health_fan_status(target_device):

    health_fan_page = target_device.controls.advanced['Health']['Fan']
    assert isinstance(health_fan_page, LawoGCFPage)
    display_gcf_page_controls(health_fan_page)


def test_ctrls_health_temp_monitoring(target_device):

    health_temp_page = target_device.controls.advanced['Health']['TempSensor']
    assert isinstance(health_temp_page, LawoGCFPage)
    display_gcf_page_controls(health_temp_page)


def test_ctrls_health_voltage_monitoring(target_device):

    health_voltage_page = target_device.controls.advanced['Health']['VoltsMonitor']
    assert isinstance(health_voltage_page, LawoGCFPage)
    display_gcf_page_controls(health_voltage_page)


def test_ctrls_health_current_monitoring(target_device):

    health_current_page = target_device.controls.advanced['Health']['AmpsMonitor']
    assert isinstance(health_current_page, LawoGCFPage)
    display_gcf_page_controls(health_current_page)
