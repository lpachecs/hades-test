# Managing Stream Routing using LDF

The starting point to creating/disconnecting stream routing using LDF is the `addresses` attribute of the target LDF device. An Address is a HOME concept where each IP sender or receiver (sord) on a single device has a corresponding Address object. When routes are created, the Address object's `Gate` attribute is exchanged between source and destination.

For simplicity, the following examples will route an audio IP sender stream to an audio IP receiver on the same device. The approach would be the same when routing between LDF instances of remote devices.

The LDF API for managing Addresses is slightly different to that of sords, controls or terminals (and this will likely change in future versions). The `DEVICE.addresses` attribute callable is still a coroutine and must therefore be awaited whilst inside an `async with` context (active connection to the device).

---

## Creating a Device Instance

```python
from ldf.production import create_home_native

DEVICE_TYPE = "A__mic8"
DEVICE_GUID = "68065da5-80ea-3863-95ee-ac2d132a4d03"
HOME_SERVERS = ["10.1.215.71"]

DEVICE = await create_home_native(
    lawo_type=DEVICE_TYPE,
    guid=DEVICE_GUID,
    client_addrs=HOME_SERVERS
)
```

---

## Listing Device Addresses

```python
# Connect + subscribe for updates from the device 
# Get addresses for all audio IP streams on the device (senders and receivers)
async with DEVICE:
    for addr in await DEVICE.addresses(type='audio'):
        print(f"{addr.ID} - {type(addr)}")
```

---

## Retrieving Source and Destination Gates

```python
# Connect to the device and get the `Gate` attribute of a specific audio IP sender and receiver by ID.
async with DEVICE:
    source_gate = next(
        addr.Gate for addr in await DEVICE.addresses(direction='tx', type='audio')
        if addr.ID.endswith('Tx-5:audio')
    )

    destination_gate = next(
        addr.Gate for addr in await DEVICE.addresses(direction='rx', type='audio')
        if addr.ID.endswith('Rx-2:audio')
    )

print(source_gate)
print(destination_gate)
```

---

## Connecting IP Streams (Addresses)

The `DEVICE.addresses.connect` coroutine is the public method to handle this. Calling `connect` will call other private functions to block until confirmation that the appropriate HOME updates have been published by the device (this can be bypassed using the `block_until_connect=False` argument).

The `connect` method requires a list of tuples, each tuple containing the Address Gate for a single source → destination route.

### Single Connection Example

```python
connection = [
    (source_gate, destination_gate),
]

async with DEVICE:
    labels = await DEVICE.addresses.connect(connection)
```

### Multiple Connections Example

```python
async with DEVICE:
    audio_srcs = [
        addr.Gate for addr in await DEVICE.addresses(direction='tx', type='audio')
    ]

    audio_dsts = [
        addr.Gate for addr in await DEVICE.addresses(direction='rx', type='audio')
    ]

    await DEVICE.addresses.connect(
        [
            (src, dst) for src, dst in zip(audio_srcs, audio_dsts)
        ]
    )
```