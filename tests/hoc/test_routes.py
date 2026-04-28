import asyncio

import pytest

from ldf.common.system.addresses import HomeControllerAddress
from ldf.models.home_controller.routes import HomeControllerRoute
from tests import log

pytestmark = [
    pytest.mark.dependency
]


def test_list_routes(hoc):

    for route in hoc.routes:
        log.info(f"{route}")
        assert isinstance(route, HomeControllerRoute)

    log.info(f"Total Routes: {len(hoc.routes)}")


def test_all_sources(hoc):

    for src in hoc.routes.sources:
        log.info(f"{src}")


def test_active_sources(hoc):
    for src in hoc.routes._active_sources():
        log.info(f"{src}")


def test_all_destinations(hoc):

    for dst in hoc.routes.destinations:
        log.info(f"{dst}")


def test_active_destinations(hoc):

    for dst in hoc.routes._active_destinations():
        log.info(f"{dst}")


async def test_wait_for_updates(hoc):

    log.info("Waiting for address updates...")
    log.info(len(hoc.routes._sords))
    await asyncio.sleep(5)
    try:
        for addr in [x for x in hoc.routes._addrs.values() if "A__mic8 - 1" in x.labels]:
            log.info(addr)
    except Exception as e:
        log.error(f"Error occurred while waiting for updates: {e}")

    log.info(len(hoc.routes._sords))


@pytest.mark.parametrize(
    "test_filter",
    [
        {"model": "A__mic8", "status": "active"},
        {"status": "idle"},
        {"is_dest": True},
        {"labels": "A__mic8 - 1"},
        {"status": "online"},
        {"status": "offline"},
    ]
)
def test_filter(hoc, test_filter):

    for addr in hoc.routes.filter(**test_filter):
        assert isinstance(addr, (HomeControllerRoute, HomeControllerAddress))
        log.info(f"{addr}")


async def test_create_audio_sender(hoc):
    info = [x.home_id for x in hoc.endpoints.filter(model="A__mic8", state="online")]
    dev = await hoc.endpoints.create_natives(info)

    async def create_audio_sender(dev):
        async with dev:
            sender = next(
                x for x in await dev.sords.create_audio(count=1, ch_count=8, label="HOC Test Sender")
            )
            # Validate that the appropriate Address update has been added to the cache
            assert [x for x in hoc.routes.filter(sord_id=sender.ID)], f"Failed to find address for {sender.ID}"
            await dev.sords.remove([sender])

    await asyncio.gather(*[create_audio_sender(dev) for dev in dev.values()])


async def test_routes_get_stiches(hoc):

    for stitch in hoc.routes._stitches:
        log.info(stitch)


async def create_route(hoc):
    src_device_id = "3Vw1NKqwla2ifVFbGmQQt2"
    dst_device_id = "3Vw1NKqwla2ifVFbGmQQt2"
    devices = await hoc.endpoints.create_natives([src_device_id, dst_device_id])
    for dev in devices.values():
        async with dev:
            src = next(x for x in await dev.sords.create_audio(count=1, ch_count=8, direction="tx", label="HOC Tx"))
            dst = next(x for x in await dev.sords.create_audio(count=1, ch_count=8, direction="rx", label="HOC Rx"))
    try:
        source = next(x for x in hoc.routes.sources if x.sord_id == src.ID)
        destination = next(x for x in hoc.routes.destinations if x.sord_id == dst.ID)
    except StopIteration:
        log.error(f"Failed to find routes for source {src.ID} or destination {dst.ID}")
        return

    route = await hoc.routes.create([
        (source, destination)
    ])
    assert route is not None, "Failed to create route"
    await asyncio.sleep(2)  # Allow some time for the route to be established
    for route in hoc.routes:
        log.info(f"Existing route: {route}")


async def disconnect_all(hoc):
    if not hoc.routes:
        pytest.skip("No routes to disconnect")

    await hoc.routes.disconnect([x for x in hoc.routes])
    await asyncio.sleep(2)  # Allow some time for the routes to be disconnected
    assert not [x for x in hoc.routes._active_sources()], "Some routes are still active"


def test_hoc_route_sords(hoc):
    log.info(hoc.routes._sords)
    pass
