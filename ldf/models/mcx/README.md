# LawoMCXDevice — Usage Guide

`LawoMCXDevice` is the model to interact with an MCX System. It provides methods for connecting to the device,
polling parameters, sending (some) commands, and performing common complex operations.

---

## Table of Contents

- [LawoMCXDevice — Usage Guide](#lawomcxdevice--usage-guide)
  - [Table of Contents](#table-of-contents)
  - [Classes Overview](#classes-overview)
  - [Connecting to an MCX Device](#connecting-to-an-mcx-device)
    - [With HOME](#with-home)
    - [Without HOME (direct IP)](#without-home-direct-ip)
    - [Disconnecting](#disconnecting)
  - [Method Reference](#method-reference)
    - [Low-Level MCX Protocol](#low-level-mcx-protocol)
    - [Asserting Values (set-and-verify helpers)](#asserting-values-set-and-verify-helpers)
    - [Button and Console Control](#button-and-console-control)
    - [Console Strip Assignment](#console-strip-assignment)
    - [Channel Bank Access](#channel-bank-access)
    - [Strip Assign Mode](#strip-assign-mode)
    - [Bus Assignment](#bus-assignment)
    - [Signal Routing](#signal-routing)
    - [Signal Metering](#signal-metering)
    - [Surround Signals](#surround-signals)
    - [Equalizer (EQ)](#equalizer-eq)
    - [AUX Sends](#aux-sends)
    - [DSP Resource Queries](#dsp-resource-queries)
    - [UHD DSP Configuration](#uhd-dsp-configuration)
    - [Snapshots](#snapshots)
    - [Presets](#presets)
    - [Productions](#productions)
    - [System Commands](#system-commands)
    - [Automation](#automation)
    - [Redundancy / Grouping](#redundancy--grouping)
  - [Unit Conversion Helper — LawoMCXDeviceHelper](#unit-conversion-helper--lawomcxdevicehelper)
  - [Errors and Exceptions](#errors-and-exceptions)
    - [Connection Errors](#connection-errors)
    - [Runtime Errors](#runtime-errors)
    - [Handling Timeout in Tests](#handling-timeout-in-tests)
  - [Complete Examples](#complete-examples)
    - [Pytest Fixture Pattern (with HOME)](#pytest-fixture-pattern-with-home)
    - [Pytest Fixture Pattern (without HOME)](#pytest-fixture-pattern-without-home)
    - [Session-Scoped Cold-Production Fixture](#session-scoped-cold-production-fixture)
    - [Full DSP Configuration](#full-dsp-configuration)
    - [EQ Configuration](#eq-configuration)
    - [Signal Routing with Cleanup](#signal-routing-with-cleanup)

---

## Classes Overview

| Class | Purpose |
|---|---|
| `LawoMCXDevice` | Main device model. Represents a single MCX console. |
| `LawoMCXDeviceHelper` | Static utility class. Converts between physical units and the MCX internal representation. |

Both are exported from `ldf.models.mcx`:

```python
from ldf.models.mcx import LawoMCXDevice, LawoMCXDeviceHelper
```

---

## Connecting to an MCX Device

This model will interact with the MCX System via two main communication layers:

- **HOME(NATS)** *optional* — Provides automatic IP resolution from a device GUID. *Only works when the MCX is registered in HOME.*
- **SystemLink** — a proprietary TCP socket protocol used for all parameter get/set operations.

### With HOME

Use `create_home_native` from `ldf.production`. This is the standard path and handles NATS
connection, endpoint population, and model setup automatically.

```python
import asyncio
from ldf.production import create_home_native
from ldf.models.mcx import LawoMCXDevice
from typing import cast

HOME_SERVERS = ['192.168.1.10']           # NATS broker addresses
MCX_GUID    = 'abcd-1234-...'            # GUID from HOME

async def main():
    device = cast(
        LawoMCXDevice,
        await create_home_native(
            lawo_type='mcx',
            guid=MCX_GUID,
            client_addrs=HOME_SERVERS,
        )
    )
    # HOME resolves the MCX IP automatically
    await device.connect()

    version = await device.get_version()
    print(f'Connected. SW version: {version}')

    await device.disconnect()

asyncio.run(main())
```

You can override automatic IP resolution by passing `host_address` to `connect()`:

```python
await device.connect(host_address='192.168.1.20')
```

### Without HOME (direct IP)

Instantiate `LawoMCXDevice` directly with `home_connection=False` and provide the IP explicitly.
No NATS broker is required.

```python
from ldf.models.mcx import LawoMCXDevice

async def main():
    device = LawoMCXDevice([], home_connection=False)
    await device.connect(host_address='192.168.1.20')
    # ...
    await device.disconnect()
```

> **Note:** `host_address` is mandatory  when `home_connection=False`. Calling `connect()`
> without it raises `ValueError`.

### Disconnecting

Always call `disconnect()` when done. It closes the SystemLink TCP connection:

```python
await device.disconnect()
```

In pytest, use a fixture that yields and disconnects in teardown:

```python
@pytest.fixture(scope='module')
async def mcx_device(request):
    device = await connect_mcx(request)
    yield device
    await device.disconnect()
```

---

## Method Reference

> **Note:** Check if an method is sync or async before calling. Async methods must be `await`ed, and sync methods must not.
If you are not sure, check if the method is only setting parameters (fire and forget) or if it needs to wait for a response from the device.
When it needs a response, it is async. When it just sends a command without waiting for confirmation, it is sync.

### Low-Level MCX Protocol

These are the building blocks that all higher-level methods use internally.
Use them when no higher-level method exists for the operation you need.

| Method | Sync/Async | Description |
|---|---|---|
| `mcx_event(m_number, n_number, data)` | sync | Fire-and-forget set. Sends a value to the device. No response is awaited. |
| `mcx_get(m_number, n_number, data_type)` | **async** | Request a value from the device and wait for the response. Returns an instance of `data_type`. |
| `wait_for(m_number, ...)` | **async** | Block until the device broadcasts an event for the given M-Number. |

**Parameters:**
- `m_number` — `MNumber` enum member or raw `int`. Identifies the parameter type.
- `n_number` — `int`. Identifies the specific instance (e.g. strip index, channel index).
- `data_type` — A `BaseDataType` subclass. Used by `mcx_get` to deserialize the response.

```python
from systemlink.common.m_lookup import MNumberLookup as MNumber
from systemlink.datamodel.base import BoolType

# Set channel 0 cut to True
device.mcx_event(MNumber.CHANNEL_CHANNEL_CUT, 0, BoolType(True))

# Read it back
result: BoolType = await device.mcx_get(MNumber.CHANNEL_CHANNEL_CUT, 0, BoolType)
assert result.value is True

# Wait for system blink (confirmation that device processed the command)
await device.wait_for(MNumber.SYSTEM_BLINK)
```

**`wait_for` optional parameters:**

| Parameter | Default | Sync/Async | Description |
|---|---|---|---|
| `open_stream` | `False` | async | Open a new subscription stream before waiting. Use when you need to catch a transient event. |
| `response_iterations` | `1` | async | How many events to collect before returning. |
| `response_timeout` | `WAIT_FOR_RESPONSE_TIMEOUT` | async | Seconds before `asyncio.TimeoutError` is raised. |

---

### Asserting Values (set-and-verify helpers)

| Method | Sync/Async | Description |
|---|---|---|
| `set_and_check(m_number, n_number, data, message, retries)` | **async** | Sets a value and verifies it was accepted. Retries once by default. Raises `AssertionError` on mismatch, `ValueError` if device does not respond. |
| `set_and_check_not(m_number, n_number, data, message)` | **async** | Sets a value and asserts the device did **not** accept it. |
| `assert_MND(m_number, n_number, data, message)` | **async** | Read-only assertion: get the current value and assert it equals `data`. |
| `assert_MND_not(m_number, n_number, data, message)` | **async** | Read-only assertion: asserts current value does **not** equal `data`. |

```python
await device.set_and_check(MNumber.CHANNEL_CHANNEL_CUT, 0, BoolType(True))
await device.assert_MND(MNumber.CHANNEL_CHANNEL_CUT, 0, BoolType(True))
```

---

### Button and Console Control

| Method | Sync/Async | Description |
|---|---|---|
| `toggle_button(m_number, n_number, hold_time)` | **async** | Press and release a button. `hold_time` defaults to `0.1 s`. |
| `toggle_button_no_wait(m_number, n_number)` | sync | Same as above but does not `await`. Sends press and release in quick succession. |
| `get_lamp_state(m_number, n_number)` | **async** | Returns the `LampState` of a button LED. |
| `toggle_button_to(m_number, n_number, state)` | **async** | Toggle the button until the lamp reaches the desired `LampState`. Max 5 attempts. |
| `toggle_button_from(m_number, n_number, state)` | **async** | Toggle the button only if the lamp is currently in `state`. Single attempt. |
| `set_button_on(m_number, n_number)` | **async** | Toggle button until lamp is no longer `LAMP_BLACK`. |
| `set_button_off(m_number, n_number)` | **async** | Toggle button until lamp is `LAMP_BLACK`. |
| `set_button_state(m_number, n_number, on)` | **async** | Convenience wrapper: `True` → `set_button_on`, `False` → `set_button_off`. |

```python
from systemlink.datamodel.console import LampState

await device.toggle_button_to(MNumber.CONSOLE_ACCESS_PAN_STICK0_REVEAL, 0, LampState.LAMP_YELLOW)
state = await device.get_lamp_state(MNumber.CONSOLE_ACCESS_PAN_STICK0_REVEAL, 0)
assert state == LampState.LAMP_YELLOW

# Reset
await device.toggle_button_to(MNumber.CONSOLE_ACCESS_PAN_STICK0_REVEAL, 0, LampState.LAMP_BLACK)
```

---

### Console Strip Assignment

Strips are the physical fader channels on the console surface.
`fu_channel` is the DSP channel (Funktionseinheit index) to assign.

| Method | Sync/Async | Description |
|---|---|---|
| `assign_strip(strip, fu_channel)` | sync | Assign DSP channel to a front strip. |
| `unassign_strip(strip)` | sync | Clear front strip assignment. |
| `assign_strip_back(strip, fu_channel)` | sync | Assign DSP channel to a back strip. |
| `unassign_strip_back(strip)` | sync | Clear back strip assignment. |
| `assign_strip_via_access(strip, fu_channel)` | **async** | Assign using the access channel workflow (hardware button simulation). |
| `multi_assign_strip(start_strip, start_fu_channel, count)` | sync | Assign a consecutive block of DSP channels to consecutive front strips. |
| `multi_unassign_strip(start_strip, count)` | sync | Clear a consecutive block of front strip assignments. |
| `multi_assign_strip_back(start_strip, start_fu_channel, count)` | sync | Same as `multi_assign_strip` for back layer. |
| `multi_unassign_strip_back(start_strip, count)` | sync | Same as `multi_unassign_strip` for back layer. |

```python
device.assign_strip(0, 0)        # strip 0 → DSP channel 0
device.multi_assign_strip(0, 4, 8)  # strips 0–7 → DSP channels 4–11
device.multi_unassign_strip(0, 8)
```

---

### Channel Bank Access

The access section controls which bank (layer) of channels is currently visible.

| Method | Sync/Async | Description |
|---|---|---|
| `mcx_toggle_bank(bank)` | sync | Toggle the bank button (0–5). Raises `ValueError` for out-of-range bank. |
| `mcx_toggle_banks(*banks)` | sync | Toggle multiple banks in sequence. |
| `mcx_set_access_bank(bank)` | sync | Alias for `mcx_toggle_bank`. |
| `mcx_get_access_bank()` | **async** | Returns the index of the currently active bank. |
| `mcx_enter_assign()` | sync | Activate assign mode on the console. |
| `mcx_cancel_assign()` | sync | Cancel assign mode. |
| `mcx_set_access_channel(access_channel)` | sync | Set the active access channel. |

---

### Strip Assign Mode

These control the strip assign workflow on the hardware surface.

| Method | Sync/Async | Description |
|---|---|---|
| `mcx_strip_assign_activate_strip_assign()` | sync | Enter strip assign mode. |
| `mcx_strip_assign_activate_insert_move()` | sync | Activate insert/move mode. |
| `mcx_strip_assign_activate_first_last()` | sync | Activate first/last mode. |
| `mcx_strip_assign_both_layer()` | sync | Apply to both layers. |
| `mcx_strip_assign_all_bank()` | sync | Apply to all banks. |
| `mcx_strip_assign_clear()` | sync | Clear strip assignments. |
| `mcx_strip_assign_clear_bank()` | sync | Clear the current bank. |
| `mcx_strip_assign_copy_bank()` | sync | Copy the current bank. |
| `mcx_strip_assign_clear_bay_iso()` | sync | **Not implemented.** Raises `NotImplementedError`. |

---

### Bus Assignment

| Method | Sync/Async | Description |
|---|---|---|
| `mcx_bus_assign(fu_channel, fu_bus, assign)` | sync | Assign/unassign a DSP channel to a bus (Sum, Group, or Aux). Detects type from `fu_bus` index. |
| `assert_mcx_bus_assign(fu_channel, fu_bus)` | **async** | Assert that the assignment is active. |
| `mcx_sum_assign(fu_channel, sum_bus, assign)` | sync | Direct Sum bus assignment by index. |
| `assert_mcx_sum_assign(fu_channel, sum_bus)` | **async** | Assert Sum assignment. |
| `mcx_group_assign(fu_channel, group, assign)` | sync | Group bus assignment by index. |
| `assert_mcx_group_assign(fu_channel, group)` | **async** | Assert Group assignment. |
| `mcx_aux_assign(fu_channel, aux, assign)` | sync | Aux bus assignment by index. |
| `assert_mcx_aux_assign(fu_channel, aux)` | **async** | Assert Aux assignment. |

```python
from systemlink.datamodel.channel import Funktionseinheiten as FU

# Assign DSP channel 0 to Sum bus 0
device.mcx_bus_assign(0, FU.FU_SUMM_BASE, True)
await device.assert_mcx_bus_assign(0, FU.FU_SUMM_BASE)

# Direct sum assign, index-based
device.mcx_sum_assign(0, 2, True)   # DSP channel 0 → sum 2
device.mcx_group_assign(0, 0, True) # DSP channel 0 → group 0
device.mcx_aux_assign(0, 1, True)   # DSP channel 0 → aux 1
```

---

### Signal Routing

| Method | Sync/Async | Description |
|---|---|---|
| `mcx_connect(source, target)` | sync | Connect `source` signal to `target` in the MCX router. Both must be `UniqueSignalAddress`. |
| `mcx_disconnect(target)` | sync | Disconnect whatever is routed to `target`. |
| `check_signal_online(fu_index)` | **async** | Returns `True` if the signal at `fu_index` is online in the router. |
| `get_fu_signal_type(fu_index)` | sync | Returns the `FunktionseinheitTypes` enum value (INP, GRP, SUM, AUX) for an FU index. |
| `add_external_signal(...)` | sync | Register an external (e.g. RAVENNA) signal in the MCX signal database. |
| `remove_external_signal(signal_type, dev_id, signal_id)` | sync | Remove a previously registered external signal. |

```python
from systemlink.datamodel.signal import SignalType, UniqueSignalAddress as USA

# Connect signal generator 0 to DSP input 0
device.mcx_connect(USA(SignalType.SigGen, 0, 0), USA(SignalType.DspInput, 0, 0))

# Disconnect
device.mcx_disconnect(USA(SignalType.DspInput, 0, 0))
```

---

### Signal Metering

| Method | Sync/Async | Description |
|---|---|---|
| `set_signal_metering_pickup(fu_index, pickup)` | sync | Set the metering pickup point using `SignalMeteringPickup` enum. |
| `get_signal_metering_pickup(fu_index)` | **async** | Get the current metering pickup setting. |
| `get_signal_metering_main_level(fu_index)` | **async** | Get the main level meter value (Lawo dB units). |
| `get_signal_metering_input_level(fu_index)` | **async** | Get the input level meter value. |
| `get_signal_metering_insert_level(fu_index)` | **async** | Get the insert level meter value. |
| `get_signal_metering_directout_level(fu_index)` | **async** | Get the direct out level meter value. |

**`SignalMeteringPickup` enum values:**

| Name | Description |
|---|---|
| `INPUT` | Pre-fader input mix output |
| `PRE_FADER` | Signal before the fader |
| `AFTER_FADER` | Signal after the fader (sum bus) |
| `DIRECT_OUT` | Direct output |

```python
device.set_signal_metering_pickup(0, LawoMCXDevice.SignalMeteringPickup.PRE_FADER)
level = await device.get_signal_metering_main_level(0)
real_db = LawoMCXDeviceHelper.from_lawo_dB(level)
```

---

### Surround Signals

| Method | Sync/Async | Description |
|---|---|---|
| `get_first_surround_signal(fu_index)` | **async** | Returns the first FU index in the surround bundle that contains `fu_index`. |
| `is_signal_part_of_surround_bundle(fu_index)` | **async** | Returns `True` if the signal is part of an active surround bundle. |
| `is_signal_surround_master(fu_index)` | sync | Returns `True` if `fu_index` is in the surround master range. |
| `get_surround_master(fu_index)` | **async** | Returns the FU index of the surround master for the given FU. |
| `get_stereo_leg(fu_index, left)` | sync | Returns the left or right FU index for a stereo pair. |
| `get_left_stereo_leg(fu_index)` | sync | Shortcut for `get_stereo_leg(fu_index, left=True)`. |
| `get_right_stereo_leg(fu_index)` | sync | Shortcut for `get_stereo_leg(fu_index, left=False)`. |

---

### Equalizer (EQ)

All EQ methods take `fu_index` (DSP channel index) and `band` (1–4). Band values
outside 1–4 raise `ValueError`.

| Method | Sync/Async | Description |
|---|---|---|
| `set_eq_on(fu_index, on)` | sync | Enable/bypass the full EQ on this channel. |
| `get_eq_on(fu_index)` | **async** | Returns `True` if EQ is enabled. |
| `set_eq_band_on(fu_index, band, on)` | sync | Enable/bypass a single EQ band. |
| `get_eq_band_on(fu_index, band)` | **async** | Returns `True` if the band is enabled. |
| `set_eq_band_type(fu_index, band, band_type)` | sync | Set the filter type (`EQBandType`). |
| `get_eq_band_type(fu_index, band)` | **async** | Get the filter type. |
| `set_eq_band_freq(fu_index, band, frequency)` | sync | Set frequency as a `MCX_FREQ` value (use `to_lawo_Hz`). |
| `get_eq_band_freq(fu_index, band)` | **async** | Get frequency as `MCX_FREQ`. |
| `set_eq_band_gain(fu_index, band, gain)` | sync | Set gain as a `MCX_LEVEL` value (use `to_lawo_dB`). |
| `get_eq_band_gain(fu_index, band)` | **async** | Get gain as `MCX_LEVEL`. |
| `set_eq_band_q(fu_index, band, q)` | sync | Set Q-factor as a `MCX_QUAL` value (use `to_lawo_Q`). |
| `get_eq_band_q(fu_index, band)` | **async** | Get Q-factor as `MCX_QUAL`. |
| `set_eq_band(fu_index, band, band_type, q, frequency, gain)` | sync | Convenience setter. All parameters are optional. Handles unit conversions internally for `q` and `frequency`. |

```python
from systemlink.datamodel.signal import EQBandType

# Enable EQ and configure band 1 as a low-shelf at 100 Hz, +3 dB
device.set_eq_on(0, True)
device.set_eq_band(
    fu_index=0,
    band=1,
    band_type=EQBandType.LOW_SHELF,
    frequency=100,                          # Hz — converted internally
    gain=LawoMCXDeviceHelper.to_lawo_dB(3), # must pass Lawo dB when using set_eq_band_gain directly
)
```

> **Note:** `set_eq_band` converts `q` and `frequency` via the helper internally.
> `gain` is passed through as-is — convert it with `to_lawo_dB` first.

---

### AUX Sends

| Method | Sync/Async | Description |
|---|---|---|
| `set_aux_gain(fu_index, dest_fu_index, gain_lawo_db)` | sync | Set the aux send level from `dest_fu_index` channel to aux bus `fu_index`. Gain must be in Lawo dB units. |
| `get_aux_gain(fu_index, dest_fu_index)` | **async** | Get the aux send level. Returns `MCX_LEVEL`. |

```python
from systemlink.datamodel.channel import Funktionseinheiten as FU

lawo_db = LawoMCXDeviceHelper.to_lawo_dB(-20)  # convert -20 dB to Lawo units
device.set_aux_gain(FU.FU_AUX_BASE + 1, 0, lawo_db)

result = await device.get_aux_gain(FU.FU_AUX_BASE + 1, 0)
real_db = LawoMCXDeviceHelper.from_lawo_dB(result.value)
```

---

### DSP Resource Queries

These query the active UHD Core for its current resource allocation.
All return integer counts.

| Method | Sync/Async | Description |
|---|---|---|
| `mcx_get_active_dsp()` | **async** | Returns the MCX internal ID of the active LDA/DSP unit. |
| `mcx_get_dsp_channel_count()` | **async** | Number of DSP input channels. |
| `mcx_get_dsp_bus_count()` | **async** | Number of DSP buses. |
| `mcx_get_dsp_listen_count()` | **async** | Number of listen (PFL/AFL) channels. |
| `mcx_get_dsp_automix_group_count()` | **async** | Number of automix groups. |
| `mcx_get_dsp_ext_key_count()` | **async** | Number of external key slots. |
| `mcx_get_dsp_talkback_count()` | **async** | Number of talkback channels. |
| `mcx_get_dsp_siggen_count()` | **async** | Number of signal generator slots. |

```python
channels = await device.mcx_get_dsp_channel_count()
buses    = await device.mcx_get_dsp_bus_count()
print(f'DSP: {channels} channels, {buses} buses')
```

---

### UHD DSP Configuration

| Method | Sync/Async | Description |
|---|---|---|
| `mcx_apply_uhd_dsp_config(inputs, groups, sums, auxes, ...)` | **async** | Apply a full DSP resource configuration. Triggers a DSP reconfiguration on the device. |
| `mcx_apply_crm_config(crm1, crm2, crmhp1, crmhp2)` | **async** | Enable/disable CRM (Control Room Monitor) outputs. |

**`mcx_apply_uhd_dsp_config` parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `inputs` | `int` | yes | Number of input channels. **Must be a multiple of 8.** |
| `groups` | `int` | yes | Number of group buses. **Must be a multiple of 8.** |
| `sums` | `int` | yes | Number of sum buses. **Must be a multiple of 8.** |
| `auxes` | `int` | yes | Number of aux sends. **Must be a multiple of 8.** |
| `automixgroups` | `int` | optional | Number of automix groups. |
| `extkeys` | `int` | optional | Number of external key slots. |
| `talkbacks` | `int` | optional | Number of talkback channels. |
| `pfl1` | `int` | optional | PFL listen bus 1 count. |
| `afl1` | `int` | optional | AFL listen bus 1 count. |
| `pfl2` | `int` | optional | PFL listen bus 2 count. |
| `afl2` | `int` | optional | AFL listen bus 2 count. |
| `crm1` | `int` | optional | CRM 1 count. |
| `crm2` | `int` | optional | CRM 2 count. |
| `crm_hp1` | `int` | optional | CRM HP 1 count. |
| `crm_hp2` | `int` | optional | CRM HP 2 count. |
| `do_check` | `bool` | optional (default `False`) | Wait 2 s and verify the device accepted the config. Raises `AssertionError` on mismatch. |
| `enable_listen` | `bool` | optional (default `True`) | Set the `listen_enabled` flag in the mixer config. |
| `afl1_surround_format` | `SurroundFormats` | optional | Surround format for AFL1. Defaults to `SURROUND_FORMAT_NONE`. |

```python
from systemlink.datamodel.audiosystem import SurroundFormats

await device.mcx_apply_uhd_dsp_config(
    inputs=32,
    groups=16,
    sums=8,
    auxes=8,
    automixgroups=2,
    extkeys=3,
    talkbacks=4,
    pfl1=2,
    afl1=8,
    afl1_surround_format=SurroundFormats.SURROUND_2D_5_1,
    do_check=True,
)
```

---

### Snapshots

Snapshots save and restore the complete console state to/from the device's internal storage.
The fileworker (background file I/O process on the MCX) must be idle before and after operations.

| Method | Sync/Async | Description |
|---|---|---|
| `is_fileworker_busy()` | **async** | Returns `True` if the fileworker is currently processing. |
| `wait_for_fileworker(timeout)` | **async** | Block until fileworker is idle. `timeout` defaults to 10 s. Raises `asyncio.TimeoutError`. |
| `get_current_snapshot()` | **async** | Returns `(folder, name)` tuple of the currently active snapshot. |
| `save_snapshot(name, snapshot_folder)` | **async** | Save the current state as a named snapshot. Includes a 2 s wait. |
| `load_snapshot(name, snapshot_folder)` | **async** | Load a snapshot by name and folder. Polls until confirmed (max 10 s). |
| `delete_snapshot(name, snapshot_folder)` | **async** | Delete a snapshot. Includes a 2 s wait. |

```python
await device.save_snapshot('my_show', 'shows')
await device.load_snapshot('my_show', 'shows')
folder, name = await device.get_current_snapshot()
assert name == 'my_show'
await device.delete_snapshot('my_show', 'shows')
```

> **Constraint:** `name` and `snapshot_folder` are each limited to **32 characters**.

---

### Presets

Presets save/restore a single DSP block parameter set (e.g. one EQ channel).

| Method | Sync/Async | Description |
|---|---|---|
| `save_preset(mn, snapshot_path_filename, snapshot_path_directory)` | sync | Save a preset for the block identified by `MNNumber`. `snapshot_path_directory` defaults to `""`. |
| `load_preset(mn, snapshot_path_filename, snapshot_path_directory)` | sync | Load a preset. |

`mn` is a `MNNumber` that combines an M-Number with an N-Number to identify a DSP block:

```python
from systemlink.common.mcx_com import MNNumber
from systemlink.common.m_lookup import MNumberLookup as MNumber

device.save_preset(MNNumber(MNumber.EU_EQU_BASE, 0), 'eq_preset_ch0')
device.load_preset(MNNumber(MNumber.EU_EQU_BASE, 0), 'eq_preset_ch0')
```

---

### Productions

Productions are full console configurations stored on the device (similar to a show file).
They include all assignments, routing, and DSP settings.

| Method | Sync/Async | Description |
|---|---|---|
| `get_current_production()` | **async** | Returns the name of the currently loaded production as a string. |
| `save_production(name)` | **async** | Save the current state as a named production. Waits for fileworker. |
| `load_production(name)` | **async** | Load a named production. Polls until confirmed (max 10 s after fileworker finishes). |
| `delete_production(name)` | **async** | Delete a named production. |

```python
await device.save_production('my_production')
await device.load_production('my_production')
current = await device.get_current_production()
assert current == 'my_production'
```

> **Note:** `name` is limited to **32 characters**.

---

### System Commands

| Method | Sync/Async | Description |
|---|---|---|
| `get_version()` | **async** | Returns a `SystemCsVersion` object representing the current software version. Also available as the `device.version` property after connecting. |
| `mcx_shutdown()` | **async** | Trigger a warm shutdown of the MCX device. |
| `mcx_shutdown_cold()` | **async** | Trigger a cold (full restart) shutdown of the MCX device. |

> These methods send fire-and-forget events. Their effect cannot be confirmed from the same connection since the device will go offline.

---

### Automation

| Method | Sync/Async | Description |
|---|---|---|
| `mcx_set_automation(state)` | sync | Enable (`True`) or disable (`False`) global automation. |

---

### Redundancy / Grouping

`LawoMCXDevice` inherits from `LawoGroupableDevice`, which provides:

| Method | Sync/Async | Description |
|---|---|---|
| `get_redundancy_group()` | **async** | Returns a group info object with `ID`, `GUID`, `LeaderID`, and `MemberIDs`. Requires HOME connection. |

```python
async with device.client:
    group_info = await device.get_redundancy_group()

if not list(group_info.MemberIDs):
    print('Not grouped')
else:
    print(f'Group leader: {group_info.LeaderID}')
```

---

## Unit Conversion Helper — LawoMCXDeviceHelper

The MCX stores all parameter values in an internal integer representation.
`LawoMCXDeviceHelper` provides static conversion methods for all common units.

| Conversion pair | `to_lawo_*` formula | `from_lawo_*` formula |
|---|---|---|
| **Hz** | `round(1638.0 × log10(Hz))` | `round(10^(lawo_Hz / 1638.0))` |
| **Q** | `round(64.0 × Q)` | `round(lawo_Q / 64.0)` |
| **s** (seconds) | `round(48000.0 × s)` | `round(lawo_s / 48000.0)` |
| **ms** (milliseconds) | `round(48.0 × ms)` | `round(lawo_ms / 48.0)` |
| **dB** | `round(32.0 × dB)` | `round(lawo_dB / 32.0, 2)` |
| **ratio** | `round(2048.0 × log10(ratio))` | `10^(lawo_ratio / 2048.0)` |
| **m** (meter) | `round(8192 × log10(m))` | `10^(lawo_m / 8192.0)` |

```python
from ldf.models.mcx import LawoMCXDeviceHelper as H

# Convert 1 kHz to Lawo internal representation and back
assert H.to_lawo_Hz(1000) == 4914
assert H.from_lawo_Hz(4914) == 1000

# Convert -20 dB
lawo_db = H.to_lawo_dB(-20)   # → -640
db      = H.from_lawo_dB(-640) # → -20.0

# Convert 48 ms delay
lawo_ms = H.to_lawo_ms(1)    # → 48
ms      = H.from_lawo_ms(48) # → 1.0
```

`LawoMCXDeviceHelper` also provides:

| Method | Sync/Async | Description |
|---|---|---|
| `create_fu_signal_string(fu_index)` | sync | Returns a human-readable string like `"INP 3"` or `"AUX 0"` for logging. |

---

## Errors and Exceptions

### Connection Errors

| Exception | When |
|---|---|
| `asyncio.TimeoutError` | `connect_systemlink` failed to establish TCP connection within 5 s. |
| `ConnectionTimout` (from `systemlink`) | No active interface found in HOME for the device. |
| `ValueError` | `connect()` called without `host_address` when `home_connection=False`. |
| `GetEndpointError` (from `ldf.production`) | HOME returned no responders for `get.endpoint` — device is likely offline. |
| `UnknownDeviceError` (from `ldf.production`) | Device type string not found in the LDF manifest. |
| `UnexpectedDeviceTypeError` (from `ldf.production`) | The produced model does not match the requested type. |

### Runtime Errors

| Exception | When |
|---|---|
| `asyncio.TimeoutError` | `mcx_get` or `wait_for` did not receive a response within the timeout. |
| `ValueError` | `set_and_check` — device responded but did not respond at all while still connected. |
| `AssertionError` | `set_and_check`, `assert_MND`, `mcx_apply_uhd_dsp_config` (with `do_check=True`) — value mismatch. |
| `TypeError` | `mcx_connect` or `mcx_disconnect` called with incorrect argument types. |
| `ValueError` | EQ band number out of range (not 1–4), bank number out of range (not 0–5), `mcx_apply_uhd_dsp_config` with counts not divisible by 8. |
| `ValueError` | `toggle_button_to` exceeded 5 attempts without reaching the desired lamp state. |
| `ValueError` | `toggle_button_from` failed — button did not change state after toggle. |
| `NotImplementedError` | `mcx_strip_assign_clear_bay_iso()` and `set_gui_page()` are not yet implemented. |

### Handling Timeout in Tests

```python
import asyncio

MAX_LOAD_TIME = 30

async with asyncio.timeout(MAX_LOAD_TIME):
    await device.load_production('my_production')
```

---

## Complete Examples

### Pytest Fixture Pattern (with HOME)

From [conftest.py](../../aulait-test-runner/tests/test-suite-mcx/conftest.py):

```python
import pytest
from typing import cast
from ldf.models.mcx import LawoMCXDevice
from ldf.production import create_home_native

HOME_SERVERS = ['192.168.1.10']
MCX_GUID     = 'your-guid-here'

@pytest.fixture(scope='module')
async def mcx_device():
    device = cast(
        LawoMCXDevice,
        await create_home_native('mcx', MCX_GUID, HOME_SERVERS)
    )
    await device.connect()
    yield device
    await device.disconnect()
```

### Pytest Fixture Pattern (without HOME)

```python
@pytest.fixture(scope='module')
async def mcx_device():
    device = LawoMCXDevice([], home_connection=False)
    await device.connect(host_address='192.168.1.20')
    yield device
    await device.disconnect()
```

### Session-Scoped Cold-Production Fixture

This pattern is used in the test suite to ensure a clean state is saved at the start,
and restored at the end, of every test session:

```python
@pytest_asyncio.fixture(scope='session', loop_scope='session', autouse=True)
async def create_coldstart_production(request):
    device = await connect_mcx(request)
    await device.save_production('autogen_test_cold_production')
    await device.disconnect()

    yield

    device = await connect_mcx(request)
    await device.load_production('autogen_test_cold_production')
    await device.delete_production('autogen_test_cold_production')
    await device.disconnect()
```

### Full DSP Configuration

From [test_enable_listen.py](../../aulait-test-runner/tests/test-suite-mcx/mcx_only/dsp_config/test_enable_listen.py):

```python
from systemlink.datamodel.audiosystem import MixerUserConfig, MixerResourceType as Type, SurroundFormats

async def test_dsp_config(mcx_device: LawoMCXDevice):
    # Save current config for cleanup
    orig_config = await mcx_device.mcx_get(MNumber.AUDIOSYSTEM_MIXER_USER_CONFIG, 0, MixerUserConfig)

    await mcx_device.mcx_apply_uhd_dsp_config(
        inputs=8, groups=16, sums=24, auxes=32,
        automixgroups=1, extkeys=3, talkbacks=5,
        pfl1=2, afl1=8, pfl2=2, afl2=4,
        afl1_surround_format=SurroundFormats.SURROUND_2D_5_1,
    )

    dsp_config = await mcx_device.mcx_get(MNumber.AUDIOSYSTEM_MIXER_USER_CONFIG, 0, MixerUserConfig)
    assert dsp_config.get_resource_count(Type.Input) == 8
    assert dsp_config.listen_enabled is True

    # Cleanup
    mcx_device.mcx_event(MNumber.AUDIOSYSTEM_MIXER_USER_CONFIG, 0, orig_config)
```

### EQ Configuration

```python
from systemlink.datamodel.signal import EQBandType

device.set_eq_on(0, True)
device.set_eq_band(
    fu_index=0,
    band=2,
    band_type=EQBandType.PEAK,
    frequency=1000,                             # Hz, converted internally
    q=2,                                        # Q factor, converted internally
    gain=LawoMCXDeviceHelper.to_lawo_dB(6),    # +6 dB in Lawo units
)

freq = await device.get_eq_band_freq(0, 2)
print(f'Band 2 freq: {LawoMCXDeviceHelper.from_lawo_Hz(freq.value)} Hz')
```

### Signal Routing with Cleanup

```python
from systemlink.datamodel.signal import SignalType, UniqueSignalAddress as USA
from systemlink.datamodel.base import MNumberType

source = USA(SignalType.SigGen, 0, 0)
target = USA(SignalType.DspInput, 0, 0)

device.mcx_connect(source, target)

check = await device.mcx_get(MNumber.SIGNAL_TARGET_MAIN_SOURCE, target.address, USA)
assert check == source

# Cleanup
device.mcx_disconnect(target)
```
