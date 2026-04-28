import pytest
from datamodel.client import client
from datamodel.endpoints import endpoints_home

from ldf.production import create_home_native
from tests import log

API_KEY_ADMIN = "l77YTwfNV7tmwXVIP4er7b"
API_KEY_USER = ""


def test_nats_client():
    """Validate that the datamodel client is of the correct type"""

    c = client.Client(addr=[])
    assert isinstance(c, client.Client)


@pytest.mark.dependency
@pytest.mark.parametrize("api_key", [API_KEY_ADMIN, API_KEY_USER])
async def test_model_api_key(api_key):

    dev = await create_home_native(
        lawo_type="A__mic8",
        guid="e573a51a-be9f-3281-8eca-712b9f8aff23",
        client_addrs=["10.1.215.71"],
        api_key=api_key
    )

    assert dev.client.api_key == api_key
    log.info(dev)
    log.info(dev.client)
    dev.endpoint.UserInfo.Label = "TOMMY TEST"
    log.info(dev.endpoint.UserInfo)
    async with dev:
        err = await endpoints_home.endpoints_set_user_info(
            dev.client,
            dev.id,
            dev.endpoint.UserInfo
        )

    # If executing test with no API Key - We expect an error
    # If an API Key is supplied - We expect no error from the set request
    assert err if api_key == "" else not err
