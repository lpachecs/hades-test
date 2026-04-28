import pytest

from tests import log

pytestmark = [
    pytest.mark.dependency
]


async def test_interface_duplicate(hoc):

    devices = await hoc.endpoints.create_natives(
        [x.home_id for x in hoc.endpoints.device.values()]
    )

    iface_ips = []
    duplicates = []
    for device in devices.values():
        for iface in device.interfaces:
            log.info(f"Checking {device.label} {iface.ip_address} for duplicate IP")
            if iface.ip_address in iface_ips and iface.ip_address != "0.0.0.0" and device.model != "Virtual Mixer":
                log.error(
                    f"!!! Duplicate IP found: {iface.ip_address} on device {device.label} interface {iface.label}"
                )
                duplicates.append(iface.ip_address)

            if device.model != "Virtual Mixer":
                iface_ips.append(iface.ip_address)

    assert not duplicates, f"Found duplicate interface IPs: {', '.join([x for x in duplicates])}"


async def test_interface_lldp(hoc):

    devices = await hoc.endpoints.create_natives(
        [x.home_id for x in hoc.endpoints.device.values()]
    )

    # switches = await hoc.endpoints.create_natives(
    #     [x.home_id for x in hoc.endpoints.switch.values()]
    # )

    for device in devices.values():
        if not device.label:
            continue
        log.info(f"{device.label}: {device.id}")
        for iface in device.interfaces:
            if (iface.lldp.chassis_id == " " and iface.lldp.port_id == " ") or iface.lldp is None:
                log.info(f"\t {iface.label}: No LLDP data")
                continue
            else:
                log.info(f"\t {iface.label}: {iface.lldp}")
