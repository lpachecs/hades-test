# Changelog

## 1.7.17

> [!WARNING]
>
> This release places `device.sords.create_audio()` as marked for deprecation - Existing
> code will continue to work using this version but this functionality will be removed in a
> later version - Please migrate to using `device.sords.create()` instead.

### Improved Endpoint Sord Creation

This release adds the `device.sords.create` method to the Sords API.
This is meant as a replacement to the current `device.sords.create_audio` function that is currently limited to managing audio sords only. The `device.sords.create` method is capable of handling all media type (VIDEO, AUDIO, META, GPIO) essences as well as the ability to create multi-flow sords and better control over attribute modification and updates

The function will accept kwargs which are Pythonic versions of the attributes of a sord ("Codec" -> "codec", "IsTieline" -> "is_tieline" etc). This includes setting mcast information.

```python
@pytest.mark.parametrize("chans", [2, 4, 6, 8, 16, 32, 64])
@pytest.mark.parametrize("frame_size", [2, 4, 6, 12, 16, 24, 32, 48])
@pytest.mark.parametrize("codec", ["L16", "L24", "L32", "AM824"])
@pytest.mark.parametrize("tieline", [True, False])
async def test_create_audio_tx_pairwise(self, built_test_device, chans, frame_size, codec, tieline):

    async with built_test_device:
        await built_test_device.sords.create(
            count=1,
            flows=["audio"],
            ch_count=chans,
            frame_size=frame_size,
            codec=codec,
            is_tieline=tieline,
        )
```

The `flows` attribute can be used to create multi-flow sords, by passing a list of strings ("audio", "video", "meta", "gpio"), the function will create all defined essences inside the created sord object.

```python
async with built_test_device:
    await built_test_device.sords.create(
        count=1,
        flows=["video", "audio", "audio", "audio", "meta"],
        ch_count=chans,
    )
```

Where kwargs are not explicitly defined, sensible default values will be used for the sord:

```python
DEFAULT_CREATE_SORD_ATTRS = {
    "label": "ldf-default-sord",
    "ch_count": 8,
    "sample_rate": 48000,
    "frame_size": 32,
    "codec": "L24",
    "rtp_payload": 98,
    "ttl": 20,
    "pri": {
        "mcast_addr": "",
        "udp_port": 5011,
    },
    "sec": {
        "mcast_addr": "",
        "udp_port": 5015,
    },
    "is_tieline": False,
    "syntonized": False,
    "delay": 12,
}
```

## 1.7.15

### SSH Client Utility

Generic Paramiko based SSH Client util implemented in `ldf.utils.ssh_client`.

### HomeController Support for AAA

HomeController now has access to a `hoc.auth` API attrirbute which provides authentication based functionality. The API provides generic dataclasses for auth related data structures as well as providing functions to create / remove `Users`, `Roles`, `Permits` and `API Keys`

## 1.7.13

### Support for AAA HOME API Keys

With the introduction of HOME v5.0 (AAA), we require that LDF now creates device objects models with an API Key value. The API key should be generated and stored in the HOME system intended for LDF operations.

Passing in an API Key value will result in all NATs messages produced by an LDF object to do so using the given key - Meaning that if the generated API Key is given `admin` scope, then the created device will be able to perform actions at this level.

The `create_home_native` function default behaviour remains unchanged but can now receive an `api_key` argument during runtime:

```python
API_KEY_ADMIN = "l77YTwfNV7tmwXVIP4er7b"

dev = await create_home_native(
    lawo_type="A__mic8",
    guid="e573a51a-be9f-3281-8eca-712b9f8aff23",
    client_addrs=["10.1.215.71"],
    api_key=API_KEY_ADMIN
)

assert dev.client.api_key == API_KEY_ADMIN
```

Since the previous release (1.7.12), which introduced the ability to create models with an external NATs client - We can also create a standalone NATs client with a given `api_key` to acheive the same functionality

```python
client = Client(
    addr=['10.1.215.66'],
    api_key="l77YTwfNV7tmwXVIP4er7b"
)

device = await create_home_native(
    lawo_type=dev_type,
    guid="ad5308b9-6707-3e73-ad4d-5bc3bbe2fa21",
    nats_client=client
)
```

## 1.7.12

### Bug Fixes

- 65: `__init__.py` should only use NullHandler and not configure handlers, levels, or formatters for logging

### ember-py Package Update

Includes update to ember_py version 1.0.5

### Global NATs client for all device models

Until now, every device model created using LDF has been assigned it's own NATs client to use when connecting to NATs servers and requesting info or subscriptions from a HOME system.

This release introduces functionality to assign a single NATs client to multiple device model instances. Allowing users to send control messages to the NATs broker without having to iterativley connect to multiple devices.

### Example (legacy)

The default behaviour remains unchanged (each device gets its own NATs client). Calling the `create_home_native` function will create new clients for each device model:

```python
    device = await create_home_native(
        lawo_type=dev_type,
        guid="ad5308b9-6707-3e73-ad4d-5bc3bbe2fa21",
        client_addrs=['10.1.215.66']
    )
```

### Example (new)

A global client object can be passed to the `create_home_native` function, this will bypass the creation of a new NATs client and assign the provided client to the `self.client` attribute of the created device.

```python
    client = Client(
        addr=['10.1.215.66']
    )

    device = await create_home_native(
        lawo_type=dev_type,
        guid="ad5308b9-6707-3e73-ad4d-5bc3bbe2fa21",
        nats_client=client
    )
```

> [!NOTE]
> Creating devices using the `HomeController.endpoints.create_natives()` will automatically assign the global client for HomeController to all created devices.
> This enables HomeController to use a single NATs client to control multiple devices

## 1.6.8

Added fixes for lifecycle functions in `HomeAppsController` and fixes for `ldf.common.connections`

## 1.6.7

`HomeAppsController` has improved functions for performing `lifecycle operations`. The new functions are gang `create/edit/start/stop/delete`.

You can choose how long to wait until the operation is complete and wether or not to block the program by raising an error:

async with hac:
  await hac.start_apps(
      app_names=list_of_apps_to_start_on_server,
      target_app_server=server_guid,
      version=APPS_VERSION,
      timeout_start='auto',
      timeout_health=None,
      blocking=False)

`HomeAppsController` now also can be given a data class to control default times on how long to wait for lifecycle operations to complete as well has how much time to wait between nats requests in seconds (see classes LifecycleTimeouts, NetworkOperationsData):

hac = HomeAppsController(
  client_addrs: clients_list,
  system_timezone=timezone.utc,
  lifecycle_timeouts=LifecycleTimeouts(create=2, start=5, healthy=15, stop=2, delete=2),
  net_data=NetworkOperationsData(request_wait=0.1)
)

`ldf/models/kero.py` Also added additional MV scaffolding for MV requests to `LawoMultiviewer`

`ldf/models/production.py` fixed device type name for power core app `"Power Core DSP App": LawoHomeNativeApp`

`tests/hac/test_app_controller.py` cotains new tests for lifecycle additions

`tests/hac/test_app_controller.py` added defualt paramers for virtual app server tests

## 1.6.66

Addresses.__call__() function is no longer a coroutine and therefore does not need awaiting - Current code may need updating.
Addresses state machine is constructed in a private method which is called an each device connection (ensuring state is always up to date)

`LawoHomeNativeFlow` objects now have a `.address_label` property which can be passed as `label` to the Addresses call:

```python
for sord in target_device.sords():
  for flow in sord.flows:
      print(device.addresses(label=flow.address.label))
```

Functionality added to `production.py` to enable gathering of endpoint IP Addresses when calling HOME.

## 1.6.2 - 2024-11-17

### MCX Updates and improvements to MCX model

## 1.5.10 - 2024-10-01

### MCX Updates according to new MCX Systemlink API

`ldf/models/mcx/mcx.py` - Updated the MCX model to work with the new MCX Systemlink API. The new SystemLink library now fixes a bug, that caused the connection to slow down
after some time. `mcx_events` don't need to be awaited anymore, as the new SystemLink Interface has introduced a send buffer in the background. In general all mcx actions that
do not wait for a response can be called without awaiting them. `mcx_get` or `set_anc_check` must still be awaited. For mor information see the
[MCX Systemlink Interface](https://ccp-tea.lawo.de/quality-assurance/mcx-systemlink-interface) repository.

### MCX Added some assert `not` functions

`ldf/models/mcx/mcx.py` - Added some assert `not` functions to the MCX model. These functions are used to check if a certain condition is not met.

## 1.5.3 - 2024-08-05

### Connect sords + QoL improvements in LawoHomeNativeAddresses

`ldf/common/connections.py` - Sord connections can now be done efficiently accross multiple devices. Added as part of the new common library

`ldf/attributes/addresses.py` - Removed depricated functionality and added a small QoL improvement. Address state is now updated on call (Meaning state will also be populated on LDF device instantiation)

See examples from unit tests in: `ldf/tests/connect_sords.py`

## 1.5.2 - 2024-07-26

### Controls attribute handles GCF + Non-GCF endpoint control types

Each LDF model can now access GCF control objects via the `device.controls.advanced` syntax. The advanced controls are accessed by the label of each page, this ensures any code can be written exactly as it appears in the HOME UI. Although this may causes issues with custom user labels in the future and we could decide to access the controls using a more permenant fixture such as ID.

e.g

```python
    device.controls.advanced['SDI Inputs']['SDI#01']['Audio']
```

### HAC Optimisations and improvements

Improved the performance of HAC in App creation and config generation (Done by getting some attributes once on __init__). General fixes and code optimisation. Added a cost table for App Server I/O.

## 1.5.0 - 2024-07-03

### VSM Gadget Server added to Device Models

LDF can now create a model of the VSM Gadget Server for automated testing against an instance (`models/vsm/gadgetserver`). This can be used for querying and creating VSM protocol translators.

The model uses an HTTP web API to communicate with the server. More info can be found in `models/vsm/gadgetserver/README.md`

## 1.4.3 - 2024-05-10

### Addresses Connect using LawoHomeNativeSords + LawoHomeNativeFlows

(DEPRICATED - See 1.5.3)

Devices can now use `LawoHomeNativeSord` or `LawoHomeNativeFlow` to make connections. This will do an address connection to the corresponding Sords or Flows. This should make connection of addresses in tests more simple and concise. See /tests/test_addresses/TestConnectSordsAndFlows for usage examples.

This is a non breaking change and legacy address.connect() functions call should continue to work as normal.

## 1.4.2

### STC + TPG Generator + HAC Improvements

`HomeAppsController` is now able to create and start a TPG for a destination sord, and create and start a STC for a sender sord. These can be used for patching in tests. Only requirement for use is to use a `LawoHomeNativeSord` See examples in `tests/test_app_controller.py::test_create_tpg_for_destination`

## 1.4.0 - 2024-04-30

### LawoMCXDevice <> System link

A new device type `LawoMCXDevice` has been introduced which is a subclass of `LawoHomeNativeDevice`. This device type is used to interact with MCX devices and provides additional functionality to interact with MCX devices via the systemlink protocol. For this purpose, a new `systemlink` dependency is introduced, developed by Lawo within the [mcx-systemlink-interface](https://ccp-tea.lawo.de/quality-assurance/mcx-systemlink-interface) repository.

## 1.3.1 - 2024-03-12

### LawoHomeNativeInput / LawoHomeNativeOutput + LawoHomeNativeControl Implementation

Similar to the previous LawoHomeNativeSord implementation, LDF now implements native objects for `Inputs`, `Outputs` and `Controls` of a given endpoint.

## 1.3.0 - 2024-03-11

### LawoHomeNativeSord Implementation

The attribute function `device.sords()` will no longer return the sords_pb2.Sord reference directly. Instead, an LDF native object type of `LawoHomeNativeSord` is returned.

The class contains the same access to data but allows a single point of maintenance for HOME datamodel changes.

Direct access to the protobuf message is still possible via `LawoHomeNativeSord.sord`

> [!NOTE]
> Future updates are planned for controls (LawoHomeNativeControl) and Inputs / Outputs (LawoHomeNativeInput / LawoHomeNativeOutput)

## 1.2.0 - 2024-02-14

### HOME Apps Controller Integration

Integrated functionality to monitor and control multiple HOME Apps on a system. Used to drive the HOME Apps automated tests

## 1.1.19 - 2024-01-03

### Device Controls + Parameters handling unity

RNDKANQA-39: More work required to allow common Controls handling between .edge + NodeSys based devices.
NodeSys devices manage a devices controlable parameters differently to how .edge and Kero devices handle any controlable parameters. Work should be done to make the LDF API as close as possible when working with either device type.

Controls attribute callable (__call__) will now return a list of Pages (with an additional `target_device.ctrls` property allowing access to the CtlAll structure) for GCF capable devices, if not the same function will return a list of endpoint.Control objects.

## 1.1.14 - 2023-12-2023

### Improved Error Handling

Duplicate address updates are now logged aws warnings instead of producing errors in the log

## 1.1.9 - 2023-10-20

### Addresses update state machine added

Address updates are now tracked so that each LDF device model has knowedge of what it is routed to and what is routed to it

### Deterministic wait for sord creation + address connection / removal

Updates to existing functions to block until significant updates are received in the local endpoint and addresses state. Existing code should be unaffected Hopefully will provide improvement to number of false failures seen in tests.

## 1.1.8 - 2023-10-17

### Improved model endpoint update handling

- Improvements to the endpoint update callback function so we do not miss updates when receiving a lot of traffic.
- Allow updates to be implemented into HOME Apps + HAC easily

## 1.1.7 - 2023-10-13

### Base device connection context manager

Implemented into LawoHomeNativeDevice class. A conext manager can now be used on the LDF model itself (previous behaviour was in datamodel.client). We now benefit from subsribing for device updates automatically whenever we connect to the NATs broker.

Usage example:

```python
async with built_test_device:
    created = await built_test_device.sords.create_audio(
        count=1,
        ch_count=2,
        label="LDF_sender_update_test"
    )
```

Output:

```bash
Created 2ch sord <MUwKbKr4cDpzhxtnFm4MPA>: src/strm0/LDF_sender_update_test-0
Update received for A__Mic8 - 1 >> update.endpoints.MUwKbKr4cDpzhxtnFm4MPA.sords.insert
Update received for A__Mic8 - 1 >> update.endpoints.MUwKbKr4cDpzhxtnFm4MPA.terminals.insert
Update received for A__Mic8 - 1 >> update.endpoints.MUwKbKr4cDpzhxtnFm4MPA.connections.insert
```

## 1.1.6 - 2023-10-12

### Timeout argument when waiting for device heartbeats

A `timeout` value in seconds can be supplied to the device.wait_for_heartbeat() function to define how long to wait before raising an error

### API Documentation

Documentation can now be produced using the docstrings located accross the entire LDF API. Documentation is located in `docs/output` and can be generated with the command: `sphinx-build -M html docs/source docs/output`

### General fixes

RNDKANQA-40: Allow filtering of sords using only `direction`

## 1.1.5 - 2023-10-05

### Improved Internal Terminals API + tests

Improved API for interacting with LDF model internal terminals (querying / connecting) and added more robust tests for validation.

### Deprecations

The original function used to create device models `create` has now been removed in favour of `create_home_native`. This is to allow for more `create...` type functions in the future.

## 1.1.4 - 2023-10-03

### Lower Python dependancy version number to 3.9.17

This was causing an issue with older packages required for test reporting

## 1.1.3 - 2023-09-27

### Wait_for_heartbeats function

Can be used to stall a test until we have received a number of heartbeats from the configured device (3 x heartbeats by default)

## 1.1.2 - 2023-09-13

### Added HOLOPLOT Controller device to production

LDF can now produce a LawoHomeNativeDevice model when given a device type of "HOLOPLOT Controller"

### General bug fixes

- Fixed issue where `remove` endpoint updates logic was inverted causing non updated terminals to be removed

## 1.1.1 - 2023-09-07

### MCX Device shell

An SSH client is now created as a class attribute (`shell`) of `mcx` device types. The client can be used to send shell commands, including mcxsh access to MCX / XCS instances

### Endpoint updates

Incoming `insert`, `change` or `remove` device updates are handled appropriately to modify an `endpoint` attribute of the device model.

Device data should now be called directly from `endpoint` which is automatically updated from incoming NATs messages. The base class method `subscribe_for_updates()` must be called per connection for updates to be applied.

Only attributes which could be changed should be defined as properties of the device model. The setters of any property should directly modify the class attribute `endpoint`

- id
- location
- application / profile (options)
- interfaces
- sords
- terminals
- connections
- controls

### Changes to model attribute API

Attribuites of a base device model (sords, interfaces, terminals etc) now have a unified syntax. Each attibute has a __call__ method which means you can call the attribute directly - Calling ttributes directly will return the dynamically updated endpoint value. You can also call for example `target_device.sords.get()` which will request the info directly from the device.

## 1.0.9 - 2023-08-24

### `create_home_native` / HomeNativeDeviceSpec

Function can be supplied with a HomeNativeDeviceSpec object to be applied to the created device model and used for validation. Device specs _should_ be written directly into device model classes (unless HOME Native)

### Updates to UHD Core / Virtual Mixer creation

When LDF creates an A__UHD Core device model, it will now also create an LDF model for each Virtual Mixer slice configured on the core. The virtual mixers can be accessed through the `mixers` attribute of the UHD Core and then by the name of the slice. For example:

```python
for sord in target_device.mixers.one.sords:
  log.info(sord)
```

The Virtual Mixer slices created within the UHD Core object are fully functional LDF models and can be used as if the `Virtual Mixer` had been created independently.

## 1.0.8

- Added functions to handle Sord>Flow SDP files (tests updated)
- Uses updated `datamodel` version numbering to match HOME v2.0

## 1.0.7

### Added Kero project applications for LDF device recipes

`create_home_native` function can now create the following Kero device types:

```python
{
  App Server: LawoAppServer,
  Virtual Mixer App: LawoVirtualMixerApp,
  Multiviewer App: LawoMultiViewerApp,
  UDX App: LawoUDXApp,
  Graphic Inserter App: LawoGraphicInserterApp,
  Test Pattern Generator App: LawoTPGApp,
  Stream Transcoder App: LawoStreamTranscoderApp,
}
```

## 1.0.4

### Added `spec` attribute to models to allow tests against expected hardware

- Defined known attributes for real device models

```python
print(device.spec)
HomeNativeDeviceSpec(
  type_number='977/40', 
  model='Local I/O', 
  terminals={
    'inputs': {'Mic/Line': 16, 'AES3': 16, 'MADI': 32}, 'outputs': {'Line': 16, 'AES3': 16, 'MADI': 32, 'Headphone': 4, 'RTW': 8}
  }, 
  flags={
    'CreateDeleteSords': True, 
    'GPIO': True, 
    'InternalRouting': True, 
    'AdmissionsControl': True, 
    'EditSenders': True, 
    'IsPhysical': True, 
    'IsStreamer': True
  }
)
```

## 1.0.3 - 2023-08-07

### General

- Removed references to datamodel.addrs

## 1.0.1 - 2023-08-07

- Added `create_home_native` function to supercede `create`.
- `create` will remain for a while
  
### Added Interfaces attribute to base models for interacting with a devices physical interface ports

- device.interfaces.get()
- device.interfaces.set()
- Interfaces can be interated over without connecting to the device client using `for i in device.interfaces: print(i.IpAddress)`
- Changes to the interfaces since init will require calling `await device.interfaces.get()` to be reflected in the iterator.

## 1.0.0 - 2023-08-05

### Added Addresses API to support basic Auto Subscribing receivers functionality

- Removed references to Datamodel/routes to support Addresses
- device.addresses.get()
- device.addresses.connect()
- device.addresses.disconnect()

### General Improvements

- Bumped major version to match HOME datamodel version
- Improved production script tasking for improved device creation time
- Improved device model code decoupling - models no longer required to have GUID at init, only the factory cares about the GUID at build time.
