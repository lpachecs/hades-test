# HomeController: Endpoint Management

The `home.endpoints` API can be used to select a combination of devices based on a criteria or iterate over all / some of the endpoints exposed to a HOME system.

```Python
for endpoint in home.endpoints:
	print(endpoint)
```

Iterating through the endpoint devices is a lightweight option to filter through discovered `DeviceListEntry` objects. We can then use `.endpoints` to create full LDF model objects:

```python
filtered_devices = [
	device for device in home.endpoints.filter(
		**{
			"model": "A__mic8", 
			"state": "online"
		}
	)
]

ldf_models = await home.endpoints.create_natives(
	[device.home_id for device in filtered_devices]
)
```

In the above example `ldf_models` will be type `dict[str, LawoHomeNativeDevice]` where the key is an HOME endpoint DeviceID and the value is the full LDF model.


## Fully Scripted System Endpoint Management Example

```python
import asyncio
import logging

from ldf.attributes.sords import LawoHomeNativeSord
from ldf.common.system.endpoints import HomeDeviceListEntry
from ldf.models.base import LawoHomeNativeDevice
from ldf.models.home_controller import HomeController

HOME_SERVERS = ["10.1.215.71"]
DEVICE_TYPE = ".edge"
DEVICE_ID = "mN8tWMjYnFtyRJMCw3PwdI"

log = logging.getLogger(__name__)


async def main() -> None:

    # Initialize the HomeController subscriptions
    home: HomeController = await HomeController.create(home_addrs=HOME_SERVERS)

    # Summary dataclasses for all entries in the HOME Device list
    device_list: list[HomeDeviceListEntry] = [dev for dev in home.endpoints]
    for dev in device_list:
        log.info(dev)

    # Create a dict of LDF models for all device types matching DEVICE_TYPE
    # accesible via a HOME Device ID
    device_objects: dict[str, LawoHomeNativeDevice]  = await home.endpoints.create_natives([
        dev.home_id for dev in device_list if dev.model == DEVICE_TYPE
    ])

    log.info(device_objects)

    # Iterate over a single devices' audio sender sord data
    single_device_obejct: LawoHomeNativeDevice = device_objects[DEVICE_ID]
    audio_sender_sords: list[LawoHomeNativeSord] = [
        sord for sord in single_device_obejct.sords(
            direction='tx',
            essence='audio'
        )
    ]
    for sord in audio_sender_sords:
        log.info(sord)

    await home.close()


if __name__ == "__main__":
    asyncio.run(main())
```