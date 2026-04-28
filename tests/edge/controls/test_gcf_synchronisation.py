import pytest

from ldf.attributes.controls import LawoGCFPage
from tests.edge import display_gcf_page_controls

pytestmark = [
    pytest.mark.dependency
]


def test_ctrls_sync(target_device):

    sync_page = target_device.controls.advanced['Synchronization']
    assert isinstance(sync_page, LawoGCFPage)
    display_gcf_page_controls(sync_page)


def test_ctrls_sync_ptp_ports(target_device):

    sync_page = target_device.controls.advanced['Synchronization']['Ptp']['Port']
    assert isinstance(sync_page, LawoGCFPage)
    display_gcf_page_controls(sync_page)


def test_ctrls_sync_ptp_ports_qsfp(target_device):

    sync_page = target_device.controls.advanced['Synchronization']['Ptp']['Port']['ra0']
    assert isinstance(sync_page, LawoGCFPage)
    display_gcf_page_controls(sync_page)


def test_ctrls_sync_ref(target_device):

    sync_page = target_device.controls.advanced['Synchronization']['RefSyncHV']
    assert isinstance(sync_page, LawoGCFPage)
    display_gcf_page_controls(sync_page)


def test_ctrls_sync_ref_720p25(target_device):

    sync_page = target_device.controls.advanced['Synchronization']['RefSyncHV']['720p25']
    assert isinstance(sync_page, LawoGCFPage)
    display_gcf_page_controls(sync_page)
