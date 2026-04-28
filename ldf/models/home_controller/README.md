# HOME Controller

## Endpoints
The Endpoints API maintains and internal cache of all endpoints discovered on a HOME system. The cache includes HOME ID, label, model, guid, state and flags (may be extended later). The equivalent to the HOME DeviceStatus data structure

```python
class HomeDeviceListEntry:
    home_id: str
    label: str
    model: str
    guid: str
    state: str
    flags: dict
```

As a rule the internal cache is only ever modified by HOME Device updates via NATs and all "get" style requests should query the cache. Ensuring the most up to date info is returned.

Once HomeControler is initialised, endpoints can be accessed using the `endpoints` attribute:

```python
HOME_IPS = ["10.1.215.10"]
hoc = HomeController(HOME_IPS)

# Access a single endpoint by it's HOME ID
device = hoc.endpoints['T2gB4aFhfNtSmmLqD0XdDO']
print(device)

# Iterate over all endpoints discovered on the system
for device in hoc.endpoints:
    print(device)

```

### Filtering Endpoints List


### Creating Models
Models allow further control over a specific device using appropriate LDF object. Creating an endpoint model gives us control over a devices senders and receivers, internal routing, input parameters and advanced controls

To create multiple LDF models use the `endpoints.create_natives` method call supplying a list of HOME device IDs. 

```python
hoc = HomeController(HOME_IPS)

# Create an LDF model for all discovered devices
# and store in dict by HOME ID
devices: dict[str, LawoHomeNativeDevice] = await hoc.endpoints.create_natives(
    [dev.home_id for dev in hoc.endpoints]
)

```

### Create / Remove HOME Proxy Devices


### Purge Device from System


## Routes
HomeController Routes are a combination of `Sords`, `Addresses` and `Stitches` (where applicable). Future work should incorporate IO Terminals.

```python
class HomeControllerRoute:
    source: HomeControllerAddress
    destination: HomeControllerAddress
    path_pri: list[HomeControllerStitch]
    path_sec: list[HomeControllerStitch]

```

| Term | Description  |
|------|--------------|
| Addresses | Represent the IP-domain sources and destinations. |
| Sords     | Network streams used to connect the source and destination Addresses (each Sord maps to an Address). |
| Stitches  | SDN-layer representation of routes through a HOME-controlled network. |

As with Endpoints, HomeController maintains an internal cache of `Sords`, `Addresses` and `Stitches` and will use this data to populate request calls.

```python
hoc = HomeController(HOME_IPS)

# Iterate over all active routes
for route in hoc.routes:
    print(route)


```

## Snapshots