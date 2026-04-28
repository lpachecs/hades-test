import pytest

from tests.edge import (ADV_CONTROLS_ROOT_PAGES, ADV_CONTROLS_SDI_INPUTS,
                        EDGE_BLADE)


@pytest.fixture()
def target_device():
    return EDGE_BLADE


@pytest.fixture(
    params=[x[1] for x in ADV_CONTROLS_SDI_INPUTS],
    ids=[x[0] for x in ADV_CONTROLS_SDI_INPUTS]
)
def target_device_input(request):
    return request.param


@pytest.fixture(params=ADV_CONTROLS_ROOT_PAGES)
def edge_adv_page(request, target_device):
    return target_device.controls.advanced[request.param]
