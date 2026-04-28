This document outlines use cases for the Lawo Device Factory (LDF) package by external departments across the wider Lawo organisation and provides guidelines for all stakeholders when working with the package.
# LDF Development Group

The following table defines the core engineers working on LDF within the QA function. All questions, changes or pull requests should go through the QA Technical Lead, including the appropriate engineer for the area of interest.

| QA Engineer | Main Area of Interest |
|-------------|----------------------|
| Tommy Sutton (Technical Lead) | HOME, .edge, HAPPS, NodeSys, GCF |
| Aaron Pereira | HOME, HAPPS |
| Tobias Kindt | MCX |
| Jan Petzold | Powercore |

# LDF Roadmap

The current roadmap for the LDF package can be viewed here: [Roadmap](../roadmaps/psg_use_cases.md)
The roadmap will be updated with features requested by PSG and agreed by QA, suggesting forecast completion dates.

# Behavioural Considerations

As the package was developed with a heavy focus on product validation, there are certain behaviours of the package which may not be ideal for use cases outside of this context.

## Device Endpoint Datamodel Cache

When a device object is created with LDF, it will automatically create a cache of vital endpoint statistics (Internal + External routing states, Entire HOME Endpoint model). When LDF is connected to an endpoint, it will subscribe to all appropriate NATS topics and update the cached data in real-time. This provides all automated test cases with closed loop validation of NATS Request/Reply + Update but could become very CPU intensive if creating and controlling many device objects in parallel.

## Blocking Timers During Creation / Deletion (Sords, Apps, Routes)

When making configuration changes to certain areas of a HOME system or endpoint device, the package utilises explicit waits for updates to be received on the appropriate NATS channels. This is to ensure that a product is always in the state intended for a test case but could also increase execution time of configuration scripts if being used to apply changes to a large production facility in the field.

Currently, the package will utilise explicit waits for the following actions:

| Action | Waits For |
|--------|-----------|
| Endpoint sender or receiver creation | Sender or Receiver information exists in the device Endpoint datamodel (as Sords) |
| Endpoint sender or receiver removal | Sender or Receiver information does not exist in the device Endpoint datamodel (as Sords) |
| Stream routing connections | Destination Address Gate information exists in the sender sord datamodel (as Src-Gate attribute) |
| IO Routing connections | Source and Destination Terminal IDs exist in device Endpoint datamodel (as Connections) |
| HOME App creation | HOME App instance exists in the HOME Devices list |
| HOME App removal | HOME App instance does not exist in the HOME Devices list |
| HOME App start | Application is started and is in "Healthy" state |
| HOME App stop | Application is no longer running on any server |
## Illegal Operations

Performing some operations using LDF will not offer the protection that HOME UI provides (illegal patching, parameter value combinations). Errors in a system or device configuration are possible if coded to do so.

# Packaging / CICD

- The LDF Python package + Container are automatically built and provided by the QA CI/CD infrastructure
- Released using semantic versioning (x.y.z)
- Any breaking changes will be signified using the release version number
- All releases will be published with change notes since previous release

# Deprecations

Deprecations in the LDF API have occurred in the past but should become less frequent as the API becomes hardened.

Any intended function deprecations will be clearly indicated in the form of CHANGELOG.md entries and log warnings when the function is called.



