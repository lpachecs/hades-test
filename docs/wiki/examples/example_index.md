# Code Examples

## Models

The LDF package contains a number of models which represent entities of the LAWO ecosystem. For information on the various models, see the links below:

### Generic Model Functions

All LDF models inherit basic functionality from `LawoHomeNativeDevice` which provides access to the following behaviours:

| Use cases                                                                              | Description                               |
| -------------------------------------------------------------------------------------- | ----------------------------------------- |
| [Endpoint Inputs & Parameter Control](device_models/input_parameter_controls.md)       | Working with device inputs and parameters |
| [Stream Routing](device_models/stream_routing.md)                                      | Managing IP stream routing and addresses  |

### Specific Model Functions

Some models are extended with additonal functionality. Further documentation is available in the table below:

| Model                                      | Description                                                             |
| ------------------------------------------ | ----------------------------------------------------------------------- |
| [MCX](../../../ldf/models/mcx/README.md)   | LawoMCXDevice model representing a physical MCX device in the ecosystem |
| [.edge](todo)                              | WIP                                                                     |
| [UHD Core](todo)                           | WIP                                                                     |

## HomeController

HomeController is a system level object capable of monitoring, configuring and managing multiple HOME functions including Endpoint management, NMOS Configuration and Snapshot creation / load

It is able to create single LDF device models and leverage the functionality at a device level for multiple devices in parallel.

| Use cases                                                                 | Description                                                       |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| [HomeController Overview](../../../ldf/models/home_controller/README.md)  | HomeController Overview                                           |
| [HomeController Init](home_controller/hoc_init.md)                        | HomeController Initialisation                                     |
| [HomeController Endpoints](home_controller/hoc_endpoint_mgmt.md)          | Using the `hoc.endpoints` API for endpoints managment             |
| [HomeController Routes](home_controller/hoc_system_routes.md)             | Using `hoc.routes` for HOME Stream Routing configuration          |
| [HomeController Snapshots](home_controller/hoc_snapshots.md)              | Using `hoc.snapshots` to create, inspect and load HOME Snapshots  |

## HomeAppsController

| Use cases                                                                     | Description                                       |
| ----------------------------------------------------------------------------- | ------------------------------------------------- |
| [HomeAppsController Overview](../../../ldf/models/apps_controller/README.md)  | HomeAppsController Overview                       |
| [HomeAppsController Init](home_apps_controller/test.md)                       |                                                   |
