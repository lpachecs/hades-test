import pytest

from ldf.attributes.controls import (LawoGCFPage, LawoHomeNativeControl,
                                     LawoHomeNativeControlValue)
from tests import log
from tests.edge import EDGE_BLADE

pytestmark = [
    pytest.mark.dependency
]


@pytest.fixture(params=[x for x in EDGE_BLADE.controls.advanced],
                ids=[x.label for x in EDGE_BLADE.controls.advanced])
def page(request):
    log.info(request.param)
    yield request.param


async def test_advanced_control_page_types(page):
    """Validates all LDF GCF page and control types"""

    assert isinstance(page, LawoGCFPage)
    assert isinstance(page.controls, dict)
    for ctl in page.controls.values():
        assert isinstance(ctl, LawoHomeNativeControl)
        assert isinstance(ctl.value, LawoHomeNativeControlValue)
        if not ctl:
            continue
        log.info(f"{ctl} > {ctl.ctl_type}")

    for _, sub_page in page:
        log.info(sub_page)
        assert isinstance(sub_page, LawoGCFPage)
        for control in sub_page.controls.values():
            if not control:
                continue
            log.info(f"{control} > {control.ctl_type}")
            assert isinstance(control, LawoHomeNativeControl)
            assert isinstance(control.value, LawoHomeNativeControlValue)

            if not sub_page.sub_pages:
                continue

            for _, sub_sub in sub_page:
                log.info(sub_sub)
                assert isinstance(sub_sub, LawoGCFPage)
                for control in sub_sub.controls.values():
                    if not control:
                        continue
                    log.info(f"{control} > {control.ctl_type}")
                    assert isinstance(control, LawoHomeNativeControl)
                    assert isinstance(control.value, LawoHomeNativeControlValue)


async def test_sync_summary(target_device):
    """Validates the sync summary"""

    ctrl = target_device.controls.advanced['Synchronization'].controls['RefLock']
    log.info(ctrl)
    async with target_device:
        for ctl in await target_device.controls.get([ctrl]):
            assert type(ctl.value()) is bool
