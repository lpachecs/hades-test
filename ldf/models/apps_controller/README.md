## HAC (Home Apps Controller)

# Intro

HAC is an object used to control and monitor Home Apps on a Home system. Examples of primary functions include:

- App creation
- App starting
- App stopping
- App deletion
- Keeping track of app state and data

The primary machnanism used is NATs requests.

# Instantiating HAC

```python
from ldf.models.apps_controller import HomeAppsController, LifecycleTimeouts, NetworkOperationsData

hac = HomeAppsController(
    HOME_SERVERS,
    lifecycle_timeouts=LifecycleTimeouts(
        create=1,
        start=5,
        healthy=10,
        stop=1,
        delete=1
    ),
    net_data=NetworkOperationsData(request_wait=0.1)
)
```

HOME_SERVERS: a list of HOME client addresses
    EG - ['10.1.215.66', '10.1.215.66', ...]
lifecycle_timeouts: For a single app, how long to wait (seconds) for an operation to complete before raising an error
    EG - HAC.lifecycle_timeouts.healthy = 10; will wait ten seconds for an app to be in the healhty state after start
net_data: Options for message based requests
    EG - HAC.net_data.request_wait = 0.1; How long HAC should wait between sending NATs requests

# Background on app creation

Any HOME App requires 3 components so it can be created then registered as a valid device on a HOME system, these are:

- A unqiue label
- The app type ID (Defined in the datamodel - apps.Templates)
- A valid configuration (Defined in the datamodel - apps.Templates)

App templates in the datamodel define the configuration options and rules to create any HOME App. HAC gets and stores them in `HAC.templates`.

HAC.templates # {'mv': apps_pb2.Template, 'udx': apps_pb2.Template, ...}

The templates themselves contain key app data such as
- IDs
- Option definitions that define a valid configuration for an app
- Descriptors used in HOME labels for that app

These valid app configuration options are defined in the datamodel and can be found in `HAC.templates[id].Options`. There is a large amount of options for some apps, and some options are invalid or newly required depending on other option selections. This can make figuring out a valid config complicated.

HAC can generate a valid app configuration without you having to do much work in `HAC.create_app`/`HAC.create_apps`. You only need to supply the app ID and the few options you want, HAC will fill out suitable defaults for the rest. See Example.

# HAC app data

HAC tracks and maintains key HOME App data on the HOME system per app. You can get important information for each home app in `HAC.data`, see `apps_controller.AppData`.

```python
async with hac: # On aenter HAC will start receiving app updates
    app_data = hac.data['My_App']
    app_data.configuration
    app_data.state
    ...
```

# Tips

There's many examples of use in LDF tests/hac which should always be up to date.

## Creating apps

# Example

Let's say we want to create:
    - A Multiviewer with an NDI output
    - A UDX with an SRT output

```python
HAC = HomeAppsController(...)

print(HAC.templates.keys()) # ['mv', 'udx', ...]
print(HAC.templates['mv'].Options) # tells me valid options for a Multiviewer
print(HAC.templates['mv'].Options) # tells me valid options for a UDX

apps_to_create = {
    'My_UDX': ('udx', {'outputVideoTransport': 'ndi'}),
    'My_Multiviewer': ('mv', {'outputVideoTransport': 'srt.264'}),
}

async with HAC:
    await HAC.create_apps(apps_to_create)
```

## Starting

Once apps are on the system, HAC can easily control them. When you start a set of apps the function waits for the app to reprort it's started and then waits for it to report that it's healthy. It will start that set of apps on one server on a target version.

# Example

```python
async with HAC:
    await hac.start_apps(
        app_names=['My_UDX', 'My_Multiviewer'], # List of apps to start by their label
        target_app_server=server_guid,          # An app server guid OR ID OR LDF device
        version=APPS_VERSION,                   # The version of HOME apps to run
        timeout_start=5,                        # How long to wait for the app to start
        timeout_health=10,                      # How long to wait for the app to report itself healthy
        blocking=True,                          # Wether or not to raise an error if timeouts take too long
    )
```

Hint: If you initialized HAC with `LifecycleTimeouts` it will use those times as defaults for waiting times per app. This applies to other lifecycle operations. If you don't want to specify timeouts at all HAC will use sensible defaults.

## Stopping

# Example

```python
async with HAC:
    await HAC.stop_apps(['My_UDX', 'My_Multiviewer'])
```

## Editing

# Example

```python
async with HAC:
    await HAC.stop_apps(['My_UDX', 'My_Multiviewer'])
    await HAC.edit_apps(
        {'My_UDX': {'outputAudioChannels': 8}, 'My_Multiviewer': {'outputVideoTransport': '2110-22'},})
```

## Deleting

# Example

```python
async with HAC:
    await HAC.delete_apps(['My_UDX', 'My_Multiviewer'])
```
