import asyncio

from ember_py import new_connection

from ldf.models.powercore import LawoPowercoreDevice
from ldf.models.powercore.sop_explorer import SopExplorer


async def main():
    host = "192.168.101.240"
    sop = SopExplorer(host)

    print("firmware update required?", sop.is_firmware_update_required())

    sop.upload_config(
        "C:\\Users\\petzolj1\\Documents\\gits\\powercore-testing\\device-configuration\\unit\\powercore.cfg"
    )

    print(">> config upload finished")

    ember = await new_connection(host)
    powercore = LawoPowercoreDevice([], ember_client=ember)
    print("CONFIG:", await powercore.get_config_name())


if __name__ == "__main__":
    asyncio.run(main())
