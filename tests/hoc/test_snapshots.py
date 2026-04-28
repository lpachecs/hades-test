import pytest

from tests import log

pytestmark = [
    pytest.mark.dependency
]


@pytest.mark.asyncio
async def test_list_snapshots(hoc):
    for snap in hoc.snapshots:
        log.info(snap)


async def test_create_snapshot(hoc):
    new_snap = await hoc.snapshots.create(
        label="Test Snapshot",
        include_ids=[],
        exclude_ids=[]
    )
    assert new_snap is not None
    log.info(f"Created snapshot: {new_snap}")


async def test_check_snapshot(hoc):
    for snap in hoc.snapshots:
        if snap.label != "Test Snapshot":
            continue
        assert await hoc.snapshots.check(
            snapshot_id=snap.home_id,
            device_ids=[]
        )


async def test_load_snapshot(hoc):

    for snap in hoc.snapshots:
        if snap.label != "Test Snapshot":
            continue
        assert await hoc.snapshots.load(
            snapshot_id=snap.home_id,
            template_id="",
            device_ids=[],
            sections=[],
            error_list=[]
        )


async def test_delete_snapshot(hoc):
    snap_ids = [
        snap.home_id for snap in hoc.snapshots if snap.label == "Test Snapshot"
    ]
    assert await hoc.snapshots.delete(snap_ids)
