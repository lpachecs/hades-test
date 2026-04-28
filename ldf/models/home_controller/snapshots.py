import logging

from datamodel.client.client import Client
from datamodel.snapshots import snapshots_home, snapshots_pb2


class HomeControllerSnapshot:

    def __init__(self, pb: snapshots_pb2.Snapshot) -> None:
        self.pb = pb
        self.home_id = pb.ID
        self.label = pb.Label
        self.updated = pb.Updated
        self.updated_time = pb.UpdatedTime
        self.compressed = pb.Compressed
        self.devices = [x for x in pb.Devices]

    def __str__(self) -> str:
        return (
            f"Snapshot ID: {self.home_id}, Label: {self.label}, "
            f"Updated: {self.updated}, Compressed: {self.compressed}, "
            f"Devices: {len(self.devices)}"
        )


class HomeControllerSnapshots:

    def __init__(self, client: Client, snaplist: list[HomeControllerSnapshot]) -> None:
        self.client = client
        self.log = logging.getLogger("HomeControllerSnapshots")
        self._snapshots = {snap.home_id: snap for snap in snaplist}

    def __iter__(self):
        return iter(snap for snap in self._snapshots.values())

    async def create(self, label: str, include_ids: list[str], exclude_ids: list[str]) -> HomeControllerSnapshot | None:
        """Create a HOME Snapshot for a given list of devices (or all if empty)

        Args:
            label (str): Human readable label for the snapshot
            include_ids (list[str]): List of device IDs to include in the snapshot
            exclude_ids (list[str]): List of device IDs to exclude from the snapshot

        Returns:
            HomeControllerSnapshot | None: The created snapshot object or None if creation failed
        """

        async with self.client:
            snap, err = await snapshots_home.snapshots_create(self.client, label, include_ids, exclude_ids)
        if err:
            self.log.error(f"Failed to create snapshot: {err}")
            return None

        new_snapshot = HomeControllerSnapshot(snap)
        return new_snapshot

    async def delete(self, snapshot_ids: list[str]) -> bool:
        async with self.client:
            deleted_ids, err = await snapshots_home.snapshots_delete(self.client, snapshot_ids)
        if err:
            self.log.error(f"Failed to delete snapshots: {err}")
            return False
        else:
            return True

    async def load(
        self,
        snapshot_id: str,
        template_id: str,
        device_ids: list[str],
        sections: list[str],
        error_list: list
    ) -> bool:
        """Trigger a snapshot load on the system.

        Partial loading is possible based on endpoint and
        section data, or a combination of both.

        Args:
            snapshot_id (str): Snapshot ID to load
            template_id (str): Unknown  # TODO: Whats this for?
            device_ids (list[str]): Endpoint IDs to apply snap load to
            sections (_type_): Endpoint section data to apply to included devices
            error_list (list): Unknown  # TODO: Whats this?

        Returns:
            bool: True if load was successful, False otherwise
        """

        self.log.info(
            f"Loading snapshot {snapshot_id} for devices {device_ids} and sections {sections}"
        )
        set_sections = snapshots_pb2.Sections()
        for s in sections:
            if hasattr(snapshots_pb2.Sections, s):
                setattr(set_sections, s, True)

        async with self.client:
            err = await snapshots_home.snapshots_load(
                self.client,
                snapshot_id,
                template_id,
                device_ids,
                set_sections,
                error_list
            )

        if err:
            self.log.error(f"Failed to load snapshot: {err}")
            return False
        else:
            return True

    async def check(self, snapshot_id: str, device_ids: list[str]) -> bool:
        """Dry run a snapshot load returning issues.

        Args:
            snapshot_id (str): Snapshot ID to check
            device_ids (list[str]): Endpoint IDs to check snap load against
        Returns:
            list[str]: List of issues found during check
        """

        self.log.info(
            f"Checking snapshot {snapshot_id} for devices {device_ids}"
        )

        async with self.client:
            err = await snapshots_home.snapshots_check(
                self.client,
                snapshot_id,
                "",
                device_ids
            )

        if err:
            self.log.error(f"Snapshot check found issues: {err}")
            return False
        else:
            return True

    async def cb_update_snapshots(self, msg) -> None:
        """Callback for snapshot updates from HOME controller.

        Args:
            msg: NATS message containing snapshot update.
        """

        op = msg.subject.split(".")[-1]
        snap_updates = snapshots_pb2.Update()
        snap_updates.MergeFromString(msg.data)
        match op:
            case "insert" | "change":
                for new_snapshot in [HomeControllerSnapshot(snap) for snap in snap_updates.Snapshots]:
                    self._snapshots[new_snapshot.home_id] = new_snapshot
                    self.log.debug(f"[update] Snapshot {new_snapshot.home_id} updated in cache")

            case "remove":
                for removed_snapshot in snap_updates.Snapshots:
                    snap_id = removed_snapshot.ID
                    try:
                        self._snapshots.pop(snap_id)
                        self.log.debug(f"[update] Snapshot: {snap_id} removed from cache")
                    except KeyError:
                        self.log.debug(f"Snapshot <{snap_id}> not found in cache during removal")
            case _:
                self.log.info(f"Received snapshot update notification {msg}")
