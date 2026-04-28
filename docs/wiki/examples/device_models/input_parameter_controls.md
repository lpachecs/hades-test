# LDF Device Inputs and Controls

## Creating Devices (GCF and Non-GCF)

```python
from ldf.production import create_home_native

HOME_SERVERS = ["10.1.215.71"]

NON_GCF_DEVICE = await create_home_native(
    lawo_type="A__mic8",
    guid="68065da5-80ea-3863-95ee-ac2d132a4d03",
    client_addrs=HOME_SERVERS
)

GCF_DEVICE = await create_home_native(
    lawo_type=".edge",
    guid="a7f9104c-2420-327b-bcb4-9a40c973d0de",
    client_addrs=HOME_SERVERS,
)
```

**Output:**
```
2025-06-19 09:44:44,334 - ldf.production - DEBUG - Create factory device <class 'ldf.models.amic.LawoAmicDevice'> w/ GUID: 68065da5-80ea-3863-95ee-ac2d132a4d03
2025-06-19 09:44:44,409 - ldf.production - INFO - Produced - <class 'ldf.models.amic.LawoAmicDevice'> | 3Vw1NKqwla2ifVFbGmQQt2 | 68065da5-80ea-3863-95ee-ac2d132a4d03 | A__Mic8 - 1 | 4.3.0.8 | RAVENNA Primary: 172.18.0.8 | RAVENNA Secondary: 172.18.2.8 |
2025-06-19 09:44:44,411 - ldf.production - DEBUG - Create factory device <class 'ldf.models.edge.LawoDotEdgeDevice'> w/ GUID: a7f9104c-2420-327b-bcb4-9a40c973d0de
2025-06-19 09:44:44,464 - ldf.production - DEBUG - !!! Device is .edge - Get SDI config
2025-06-19 09:44:44,498 - ldf.production - INFO - Produced - <class 'ldf.models.edge.LawoDotEdgeDevice'> | mN8tWMjYnFtyRJMCw3PwdI | a7f9104c-2420-327b-bcb4-9a40c973d0de | QA.edge Blade 2 [SG1] | v3.1.53 | MGMT1: 172.18.10.33 | MGMT2: 0.0.0.0 | SFP1: 172.18.0.33 | SFP2: 172.18.2.22 |
```

---

## Device Inputs

Each `LawoHomeNativeDevice` type has an `inputs` attribute that can be used to iterate over a device's physical inputs. Each physical input is itself a `LawoHomeNativeInput` class that is used to access controllable parameters and values for specific input attributes.

Calling the `inputs` attribute will generate a dictionary of all inputs on the device structured as `{label: input_object}`.

### Iterating Through Device Inputs

```python
# Iterate through for input labels
for device in [NON_GCF_DEVICE, GCF_DEVICE]:
    print(device)
    for label, ip in device.inputs().items():
        print(label, ip.path, type(ip))
```

**Output:**
```
<class 'ldf.models.amic.LawoAmicDevice'> | 3Vw1NKqwla2ifVFbGmQQt2 | 68065da5-80ea-3863-95ee-ac2d132a4d03 | A__Mic8 - 1 | 4.3.0.8 | RAVENNA Primary: 172.18.0.8 | RAVENNA Secondary: 172.18.2.8 |
Mic/Line-1 src/micline0/0 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
Mic/Line-2 src/micline0/1 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
Mic/Line-3 src/micline0/2 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
Mic/Line-4 src/micline0/3 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
Mic/Line-5 src/micline0/4 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
Mic/Line-6 src/micline0/5 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
Mic/Line-7 src/micline0/6 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
Mic/Line-8 src/micline0/7 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
<class 'ldf.models.edge.LawoDotEdgeDevice'> | mN8tWMjYnFtyRJMCw3PwdI | a7f9104c-2420-327b-bcb4-9a40c973d0de | QA.edge Blade 2 [SG1] | v3.1.53 | MGMT1: 172.18.10.33 | MGMT2: 0.0.0.0 | SFP1: 172.18.0.33 | SFP2: 172.18.2.22 |
sdiIn1 SdiInput.#sdiIn1 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
sdiIn2 SdiInput.#sdiIn2 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
sdiIn3 SdiInput.#sdiIn3 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
sdiIn4 SdiInput.#sdiIn4 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
sdiIn5 SdiInput.#sdiIn5 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
sdiIn6 SdiInput.#sdiIn6 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
sdiIn7 SdiInput.#sdiIn7 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
sdiIn8 SdiInput.#sdiIn8 <class 'ldf.attributes.inputs.LawoHomeNativeInput'>
```

---

## Accessing Input Controls

Accessing the `LawoHomeNativeInput` for a specific input will allow control of any parameters assigned to the input.

```python
# Access a specific input object using input label

non_gcf_ip = NON_GCF_DEVICE.inputs['Mic/Line-6']
gcf_ip = GCF_DEVICE.inputs['sdiIn6']

for term in [non_gcf_ip, gcf_ip]:

    # Iterate through available input paths
    print(term.path)
    for ctl in term.controls():
        print(ctl, type(ctl))
```

**Output:**
```
src/micline0/5
MicLine0/5/LineMode <class 'str'>
MicLine0/5/EffectiveGain <class 'str'>
MicLine0/5/UniGain <class 'str'>
MicLine0/5/UniGainOffset <class 'str'>
MicLine0/5/Microphone/Gain <class 'str'>
MicLine0/5/Microphone/GainOffset <class 'str'>
MicLine0/5/Microphone/LowCutFrequency <class 'str'>
MicLine0/5/Microphone/Pad <class 'str'>
MicLine0/5/Microphone/PhantomPower <class 'str'>
MicLine0/5/Microphone/PhantomPowerOverload <class 'str'>
MicLine0/5/Line/Gain <class 'str'>
MicLine0/5/Line/GainOffset <class 'str'>
SdiInput.#sdiIn6
	-- Mode                                     >> SdiInput.#sdiIn6.Mode = 0 <class 'ldf.attributes.controls.LawoHomeNativeControl'>
	-- IpMode                                   >> SdiInput.#sdiIn6.IpMode = 0 <class 'ldf.attributes.controls.LawoHomeNativeControl'>
	-- SdiMode                                  >> SdiInput.#sdiIn6.SdiMode = 0 <class 'ldf.attributes.controls.LawoHomeNativeControl'>
	-- Standard                                 >> SdiInput.#sdiIn6.Standard = 0 <class 'ldf.attributes.controls.LawoHomeNativeControl'>
	-- BncStandard                              >> SdiInput.#sdiIn6.BncStandard = 0 <class 'ldf.attributes.controls.LawoHomeNativeControl'>
	-- LoopbackStandard                         >> SdiInput.#sdiIn6.LoopbackStandard = 0 <class 'ldf.attributes.controls.LawoHomeNativeControl'>
	-- LoopbackEnable                           >> SdiInput.#sdiIn6.LoopbackEnable = False <class 'ldf.attributes.controls.LawoHomeNativeControl'>
	-- LoopbackSource                           >> SdiInput.#sdiIn6.LoopbackSource = 0 <class 'ldf.attributes.controls.LawoHomeNativeControl'>
	-- ForcePsf                                 >> SdiInput.#sdiIn6.ForcePsf = False <class 'ldf.attributes.controls.LawoHomeNativeControl'>
	-- Compression                              >> SdiInput.#sdiIn6.Compression = 0 <class 'ldf.attributes.controls.LawoHomeNativeControl'>
	-- Label                                    >> SdiInput.#sdiIn6.Label =  <class 'ldf.attributes.controls.LawoHomeNativeControl'>
```

---

## Working with Control Objects

Once we have a list of the controls available to a device input, this `path` can be used to set the control to a desired value. Accessing an input control explicitly will yield a `LawoHomeNativeControl` object that we use to modify the specified control for the input.

### Accessing a Control Object

```python
# Access a controllable object for the input parameter
ip_6_pad_ctl = DEVICE.controls['MicLine0/5/LineMode']
print(type(ip_6_pad_ctl))
print(ip_6_pad_ctl)
```

### Modifying and Setting a Control

```python
# Change the value of the control
ip_6_pad_ctl.value.pb = False
print(ip_6_pad_ctl.value())

# Set the control via NATS request
async with DEVICE:
    await DEVICE.controls.set([ip_6_pad_ctl])
```

### Viewing Control Values

```python
# Access a controllable object for the input parameter
ip_6_pad_ctl = device.controls['MicLine0/5/LineMode']
print(ip_6_pad_ctl)
print(ip_6_pad_ctl.value())
```

---

## Device Input Controls / Parameters

```python
for device in [NON_GCF_DEVICE, GCF_DEVICE]:
    async with device:
        print(device.controls())
```

---

## Modify Multiple Controls

We can send modified control requests for multiple device parameter changes in a single message.

```python
# Set all Microphone gain parameters
all_mic_gain_ids = [
    x.path for x in DEVICE.controls().values()
    if x.label == "MicLine/Microphone/Gain"
]

# Get and modify control object for each ID
edited_ids = []
for ctl_id in all_mic_gain_ids:
    ctl = DEVICE.controls[ctl_id]
    ctl.value = 10
    edited_ids.append(ctl)

# Send all modified controls at once
async with DEVICE:
    await DEVICE.controls.set(edited_ids)
```