## PSG Use Cases

See: [LDF External Use Agreement](../legal/external_usage_agreement.md)

Required use cases were derived from the PSG document: _Global tooling for Lawo device control and configuration_

**Note:**

- Below table requires prioritisation
- Non-existent work needs planning

### Feature Requirements Matrix

|Expectation|Examples|Exists|Agreed Date (Est)|Comment|
|---|---|---|---|---|
|Endpoint device upgrade / downgrade|-|-|Q4 2026|Work ongoing to implement generic Paramiko class. Preferably performed in parallel|
|LDF can spin up virtualised .edge and HAPPS|-|-|Q4 2026|-|
|Inventory management for devices with the ability to force them to a specific software/firmware version|-|-|Q2 2026: Documented in Wiki|Requires additional development to control the app lifecycle around the requested change|
|Access monitoring and visibility-related data like log files and metrics, including alarm triggers for further actions|Grafana|-|Q4 2026: Log introspection also required by QA|Hook into existing metrics produced by endpoint: Health check function, Dashboard Persistence, Log file streaming (e.g. to Loki)|
|Allow API hooks for upstream tools (such as Netbox)|Netbox|✓ / -|2027|Functionality should be defined further - Specifics about API hooks. Pertains more to tools developed using LDF (Not LDF itself)|
|More protection against accessing deprecated GCF controls|-|-|-|More definition required. Sending malformed or incorrect data to devices is a requirement of the QA use case|
|~~Any API-related function must support parallel requests and should spawn long-running tasks into subprocesses~~|-|✓|-|Batched requests. LDF is inherently Async|
|~~Get basic endpoint info~~|Label, Location, Software / Hardware version|✓|-|-|
|~~Bring endpoint devices into a desired state~~|IP Addresses, Tx Multicast Addresses, Tx Multicast UDP ports, PTP Settings, NTP Settings, DNS Settings|✓|-|-|
|~~Factory reset of endpoint devices~~|-|✓|-|Simple for GCF based devices|
|~~Control over parametric value of endpoint features~~|Frame Sync pixel offset|✓|-|-|
|~~Validation of expected vs actual endpoint state / Save a specific device state and restore it entirely~~|-|✓|-|Preferably applied to same device or like-like device. **Functionality should be managed by HOME. LDF Can create/recall snapshots via HOME API**|
|~~Direct (natively in the tool) or indirect interaction (API) possibilities with CI/CD pipelines like Jenkins, GitHub Actions, etc.~~|Jenkins, Gitea / Github actions|✓|14 Aug 2025| LDF delivered as a container - Allowing deployment in CI/CD pipelines in Jenkins or Github actions|
|~~Refactor log levels to accommodate scripts used outside of QA (Reduce it!)~~|-|✓|06 Nov 2025|Logging chatter reduced in LDF v1.7.0|
