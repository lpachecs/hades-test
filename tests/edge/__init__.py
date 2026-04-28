import asyncio

import pytest

from ldf.attributes.controls import LawoGCFPage, LawoHomeNativeControl
from ldf.production import create_home_native
from tests import log
from tests.user_config import HOME_SERVERS, TEST_DEVICES_GUIDS

try:
    EDGE_BLADE = asyncio.run(
        create_home_native(
            lawo_type='.edge',
            guid=TEST_DEVICES_GUIDS['.edge'],
            client_addrs=HOME_SERVERS
        )
    )
except KeyError:
    pytest.skip("No .edge device found in TEST_DEVICES_GUIDS")

ADV_CONTROLS_ROOT_PAGES = [page.label for page in EDGE_BLADE.controls.advanced]
ADV_CONTROLS_SDI_INPUTS = [page for page in EDGE_BLADE.controls.advanced['SdiInput']]


def display_gcf_page_controls(page: LawoGCFPage):
    """Display the controls for a given GCF page"""

    log.info(page)
    for ctrl in page.controls.values():
        log.info(ctrl)
        assert type(ctrl) is LawoHomeNativeControl

    for _, sub_page in page:
        if not sub_page.is_parent():
            log.info(sub_page)
            for ctrl in sub_page.controls.values():
                log.info(ctrl)
                assert type(ctrl) is LawoHomeNativeControl
        else:
            display_gcf_page_controls(sub_page)
