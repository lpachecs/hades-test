import json

import pytest

from tests import log

pytestmark = [
    pytest.mark.dependency
]


def test_hoc_endpoints_dict(hoc):
    log.info(json.dumps(hoc.endpoints.to_dict(), indent=4))


def test_hoc_route_dict(hoc):
    log.info(json.dumps(hoc.routes.to_dict(), indent=4))
