# VSM Gadgetserver LDF Integration

This model tries to integrate the VSM Gadgetserver with the LDF.

## Web Services

The web services try to integrate the VSM Gadgetserver API.

The API is documented in the [VSM Gadgetserver API](./APIDocumentation.yml). written in OpenAPI 3.0.

## Windows Services

The Windows services try to integrate the VSM Gadgetserver Host.
You can start, stop or restart the VSM Gadgetserver Service.

### Installation

To interact with the Windows services, we use the WinRM service in Windows. This service must be
activated and configured in the Windows machine.
It must be enabled and allow Basic Authentication. The following steps describe a way to enable it:
1. Open a PowerShell window as an administrator.
2. Run the following command:
```powershell
winrm quickconfig
```
3. Answer `Y` to all the questions if winrm is not already configured.
4. Run the following command to activate Basic Authentication:
```powershell
winrm set winrm/config/service/auth '@{Basic="true"}'
```
5. Run the following command to allow unencrypted traffic:
```powershell
winrm set winrm/config/service '@{AllowUnencrypted="true"}'
```
6. Run the following command to allow the service to listen on any IP address:
```powershell
winrm set winrm/config/service '@{Address="*"}'
```
7. Restart the WinRM service:
```powershell
Restart-Service WinRM
```

