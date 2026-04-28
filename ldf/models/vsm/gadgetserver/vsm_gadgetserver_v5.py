"""Device model for the VSM GadgetServer v5."""

import logging
import time
from typing import Any

import requests
import winrm
from requests.auth import HTTPBasicAuth

from ldf.models.vsm.gadgetserver.vsm_gadgetserver_resources import (
    Protocol, ProtocolFactory, ResourceData, ResourceTopics, ResourceType,
    ServerNode, ServerNodeLicense)

# DEV INFO for winrm:
# To use winrm on the Windows machine, you need to enable the WinRM service
# and enable Basic Authentication. You can do this by the following steps:
# 1. Open a PowerShell window as an administrator.
# 2. Run the following command: `winrm quickconfig`
# (3. Run the following command: `winrm set winrm/config/service/auth @{Basic="true"}`)
# (winrm set winrm/config/service @{AllowUnencrypted="true"})
#   - This did not really worked for me, so I had to do the following:
# 3. Go to `Local Group Policy Editor` -> `Computer Configuration` -> `Administrative Templates` -> `Windows Components`
# -> `Windows Remote Management (WinRM)` -> `WinRM Service`
# 4. Enable `Allow Basic authentication`
# 5. Allow `Unencrypted traffic` (for testing purposes)
# 6. Restart the WinRM service: `Restart-Service WinRM`
# 7. done.


DEFAULT_WINDOWS_SERVICE_NAME = "'vsmGadgetServer.NET (64 Bit)'"
DEFAULT_WINDOWS_PROCESS_NAME = "vsmGadgetServer"
DEFAULT_WINDOWS_DATA_DIR = r"D:\vsm\vsmGadgetServer.Net"
DEFAULT_SCHEMA = "https"
DEFAULT_PORT = 50080


# Endpoints
CONNECT = "/dex/connect"
RESOURCE_HANDLES = "/dex/resourceHandles"
RESOURCE_DATA = "/dex/resourceData"
RESOURCE = "/dex/resource"
LICENSE = "/dex/license"
JOIN = "/dex/join"
ARTICLE = "/dex/article"


def _wait_until(somepredicate, timeout, period=0.25):
    mustend = time.time() + timeout
    while time.time() < mustend:
        # if isinstance(somepredicate, bool):
        if somepredicate:
            return True
        # if somepredicate(*args, **kwargs):
        #     return True
        time.sleep(period)
    return False


class VsmGadgetServerV5:
    def __init__(
        self,
        address,
        username,
        password,
        port=DEFAULT_PORT,
        schema=DEFAULT_SCHEMA,
        service_name=DEFAULT_WINDOWS_SERVICE_NAME,
        process_name=DEFAULT_WINDOWS_PROCESS_NAME,
        data_dir=DEFAULT_WINDOWS_DATA_DIR,
    ):
        self.address = address
        self.username = username
        self.password = password
        self.session = winrm.Session(address, auth=(username, password))
        self._server_hostname = None
        self._port = port
        self._schema = schema
        self._service_name = service_name
        self._process_name = process_name
        self._data_dir = data_dir
        self._log = logging.getLogger(f"{__name__}:{self.address}")
        self.web_session = requests.session()
        self.auth = HTTPBasicAuth(username, password)
        self._authenticate_once()

    # ---------------------------------------------------------------------------- #
    #                                 WEB SERVICES                                 #
    # ---------------------------------------------------------------------------- #
    @property
    def url(self):
        return f"{self._schema}://{self.username}:{self.password}@{self.address}:{self._port}"

    @property
    def server_hostname(self) -> str:
        return self.get_server_hostname()

    def _web_connect(self):
        url = f"{self.url}{CONNECT}"
        self._log.debug("Post request to %s", url)
        response = self.web_session.post(url, timeout=5, verify=False)
        if not response.ok:
            self._log.error(
                "Connection failed, code %d, text: %s", response.status_code, response.text
            )
            raise ValueError(f"Failed to connect (Code {response.status_code}): {response.text}")
        return response.json()

    def get_service_hostname(self) -> str:
        if self.status_service:
            response = self._web_connect()
            service_hostname = response["SessionHost"]["ServiceHostname"]
            self._log.debug("Request service hostname: %s", service_hostname)
            return service_hostname

        raise ValueError(f"Service {self._service_name} is not running")

    def get_server_hostname(self) -> str:
        if self._server_hostname is None:
            result = self.session.run_ps("$env:computername")

            if result.status_code == 0:
                self._server_hostname = result.std_out.decode('utf-8').strip()
            else:
                raise RuntimeError(f"Failed to get hostname: {result.std_err.decode('utf-8')}")

        return self._server_hostname

    # Authenticate against the Webserver. First Post will always raise a 401 and then authenticate.
    def _authenticate_once(self) -> None:
        try:
            response = self.web_session.post(self.url, auth=self.auth, verify=False)
            if response.status_code == 401:
                self._re_authenticate()
                response = self.web_session.post(self.url, auth=self.auth, verify=False)

            self._log.debug("Authenticate against %s", self.url)
            response.raise_for_status()  # Raises an error if the request failed
            print(f"POST request successful: {response.status_code}")

        except requests.exceptions.HTTPError as e:
            print(f"HTTP error occurred: {e}")

        except requests.exceptions.RequestException as e:
            print(f"Error making POST request: {e}")

    def _re_authenticate(self):
        """Resets the session to handle re-authentication after a 401 error."""
        self.web_session.close()  # Close the old session
        self.web_session = requests.Session()  # Create a new session
        print("Re-authenticated and created a new session")

    # ---------------------------------- HANDLE ---------------------------------- #

    def _get_handles(self, resource_type: ResourceType) -> list[tuple[str, ResourceType]]:
        url = f"{self.url}{RESOURCE_HANDLES}"
        self._log.debug("Post request to %s", url)
        response = self.web_session.post(url, json={"Types": resource_type.value}, timeout=5, verify=False)
        if not response.ok:
            self._log.error(
                "Connection failed, code %d, text: %s", response.status_code, response.text
            )
            raise ValueError(f"Failed to get handles (Code {response.status_code}): {response.text}")
        return [
            (handle["Handle"], ResourceType(handle["Type"]))
            for handle in response.json()["Resources"]
        ]

    def get_handles_by_type(self, resource_type: ResourceType) -> list[tuple[str, ResourceType]]:
        """Get all handles of a specific resource type.

        Args:
            resource_type (ResourceType): You can use the ResourceType Enum to specify the type.

        Returns:
            list[tuple[str, ResourceType]]: List of tuples with the handle and the resource type.
                Since you can have multiple types, you get a list of tuples with the type.
        """
        return self._get_handles(resource_type)

    # --------------------------------- RESOURCE --------------------------------- #

    def get_resources_by_handles(self, handles: list[str]) -> dict:
        """Get the resources by their handles.

        Args:
            handles (list[str]): List of handles to get the resources from.

        Returns:
            dict: A dictionary containing the requested resources.
        """
        url = f"{self.url}{RESOURCE_DATA}"
        self._log.debug("Post request to %s", url)
        response = self.web_session.post(url, json={"Handles": handles}, timeout=5, verify=False)
        if not response.ok:
            self._log.error(
                "Connection failed, code %d, text: %s", response.status_code, response.text
            )
            raise ValueError(f"Failed to get resources (Code {response.status_code}): {response.text}")
        return response.json()

    def get_resources_by_type(self, resource_type: ResourceType) -> dict[Any, Any]:
        """Get all resources of a specific type.

        Args:
            resource_type (ResourceType): You can use the ResourceType Enum to specify the type.

        Returns:
            dict: A dictionary containing the requested resources.
        """
        handles = self._get_handles(resource_type)
        return self.get_resources_by_handles([handle[0] for handle in handles])

    def get_resource_by_handle(self, handle: str) -> dict:
        """Get a single resource by its handle.

        Args:
            handle (str): Handle of the resource to get.

        Returns:
            dict: A dictionary containing the requested resource.
        """
        return self.get_resources_by_handles([handle])["ResourceData"]

    # ------------------------------- RESOURCE TYPE ------------------------------ #

    def get_resource_type_by_handle(self, handle: str) -> ResourceType:
        """Get the resource type by its handle. Resource type is the parent type
        of the individual resource.

        Args:
            handle (str): Handle of the resource to get the type from.

        Raises:
            ValueError: If the handle is not found.

        Returns:
            ResourceType: The resource type of the handle.
        """
        all_handles = self.get_handles_by_type(ResourceType.ALL)
        for h in all_handles:
            if h[0] == handle:
                return ResourceType(h[1])
        raise ValueError(f"Handle {handle} not found")

    def get_protocol_factory_by_handle(self, handle: str) -> ProtocolFactory:
        """Get a ProtocolFactory by its handle.

        Args:
            handle (str): Handle of the ProtocolFactory to get.

        Returns:
            ProtocolFactory: The requested ProtocolFactory.
        """
        resource = self.get_resource_by_handle(handle)
        resource_data = ResourceData(dictionary=resource)
        return resource_data.protocol_factories[0]

    def get_protocol_by_handle(self, handle: str) -> Protocol:
        """Get a Protocol by its handle.

        Args:
            handle (str): Handle of the Protocol to get.

        Returns:
            Protocol: The requested Protocol.
        """
        resource = self.get_resource_by_handle(handle)
        resource_data = ResourceData(dictionary=resource)
        return resource_data.protocols[0]

    def get_server_node_by_handle(self, handle: str) -> ServerNode:
        """Get a ServerNode by its handle.

        Args:
            handle (str): Handle of the ServerNode to get.

        Returns:
            ServerNode: The requested ServerNode.
        """
        resource = self.get_resource_by_handle(handle)
        resource_data = ResourceData(dictionary=resource)
        return resource_data.server_nodes[0]

    def update_ressource_type(self, ressource: ResourceTopics):
        """Update a ressource on the VSM GadgetServer.

        Args:
            ressource (ResourceTopics): The ressource to update.

        Returns:
            _type_: The updated ressource.
        """
        url = f"{self.url}{RESOURCE_DATA}"

        json_data = ressource.put_data_json()
        response = self.web_session.put(
            url,
            data=json_data,
            timeout=5,
            verify=False,
            headers={"Content-Type": "application/json"},
        )
        if not response.ok:
            self._log.error(
                "Connection failed, code %d, text: %s", response.status_code, response.text
            )
            return None
        return response.json()

    def create_protocol(self, ressource: Protocol) -> Protocol:
        """Create a new Protocol on the VSM GadgetServer.

        Args:
            ressource (Protocol): Add ProtocolFactory Handle and Settings to add.

        Returns:
            Protocol: The new generated Protocol
        """
        url = f"{self.url}{RESOURCE}"

        json_data = ressource.post_data_json()
        response = self.web_session.post(
            url,
            data=json_data,
            timeout=5,
            verify=False,
            headers={"Content-Type": "application/json"},
        )
        if not response.ok:
            self._log.error(
                "Connection failed, code %d, text: %s", response.status_code, response.text
            )
            raise ValueError(f"Failed to create protocol (Code {response.status_code}): {response.text}")
        return Protocol(dictionary=response.json()["Data"]["Protocols"][0])

    def delete_ressource(self, handle: str) -> bool:
        """Delete a ressource on the VSM GadgetServer.

        Args:
            handle (str): The handle of the ressource to delete.

        Returns:
            bool: True if the ressource was deleted successfully, False otherwise.
        """
        ressource_type = self.get_resource_type_by_handle(handle)
        self._log.info("Deleting ressource %s of type %s", handle, ressource_type.name)
        url = f"{self.url}{RESOURCE}?handle={handle}&type={ressource_type.value}"
        response = self.web_session.delete(url, timeout=60, verify=False)
        if not response.ok:
            self._log.error(
                "Connection failed, code %d, text: %s", response.status_code, response.text
            )
            return False
        return True

    def get_license(self) -> ServerNodeLicense:
        """Get the license of the VSM GadgetServer.

        Returns:
            License: The license of the VSM GadgetServer.
        """
        url = f"{self.url}{LICENSE}"
        response = self.web_session.get(url, timeout=5, verify=False)
        if not response.ok:
            self._log.error(
                "Connection failed, code %d, text: %s", response.status_code, response.text
            )
            raise ValueError(f"Failed to get license (Code {response.status_code}): {response.text}")

        return ServerNodeLicense(dictionary=response.json()["License"])

    def join_server_cluster(self, ip_or_hostname: str):
        server_handles = self.get_handles_by_type(ResourceType.SERVERNODE)
        local_server: ServerNode = ServerNode()

        for server_handle in server_handles:
            server_node = self.get_server_node_by_handle(server_handle[0])
            if server_node.server_node.is_local_server:
                local_server = server_node
                break
            elif server_handle == server_handles[-1]:
                raise ValueError("Local Server not found")

        url = f"{self.url}{JOIN}?handle={local_server.handle}&ipOrHostName={ip_or_hostname}"
        response = self.web_session.get(url, timeout=5, verify=False)
        if not response.ok:
            self._log.error(
                "Connection failed, code %d, text: %s", response.status_code, response.text
            )
            raise ValueError(f"Joining Server Cluster failed: {response.text}")

    def get_article(self, ressource_handle: str) -> str:
        """Get the documentation of a ressource.

        Args:
            ressource_handle (str): Handle of the ressource to get the documentation from.

        Returns:
            str: The documentation of the ressource in markdown format.
        """
        url = f"{self.url}{ARTICLE}?handle={ressource_handle}"
        response = self.web_session.get(url, json={"Handles": [ressource_handle]}, timeout=5, verify=False)
        if not response.ok:
            self._log.error(
                "Connection failed, code %d, text: %s", response.status_code, response.text
            )
            raise ValueError(f"Failed to get article (Code {response.status_code}): {response.text}")

        return response.json()["HelpFileMd"]

    def get_changelog(self) -> str:
        """Get the changelog of the VSM GadgetServer.

        Returns:
            str: Changelog of the VSM GadgetServer in markdown format.
        """
        return self.get_article("Changelog")

    # ---------------------------------------------------------------------------- #
    #                               WINDOWS SERVICES                              #
    # ---------------------------------------------------------------------------- #

    @property
    def status_service(self) -> bool:
        """Check if the service is running.

        Returns:
            bool: True if the service is running, False otherwise.
        """
        answer = self.session.run_ps(
            f"(Get-Service {self._service_name}).Status -eq 'Running'"
        ).std_out
        answer = answer.decode("utf-8").strip()
        self._log.info("Service status: %s", answer)
        return answer == "True"

    def start_service(self):
        """Start the service.
        """
        self._log.info("Starting service %s", self._service_name)
        self.session.run_ps(f"Start-Service {self._service_name}")
        # Wait until service status is up running or timeout
        _wait_until(self.status_service, 30)
        self._authenticate_once()

    def stop_service(self):
        """Stop the service.
        """
        self._log.info("Stopping service %s", self._service_name)
        self.session.run_ps(f"Stop-Service {self._service_name}")
        _wait_until(lambda: not self.status_service, 20)

    def kill_service(self):
        """Kill the service.
        """
        self._log.info("Killing service %s", self._service_name)
        self.session.run_ps(f"Stop-Process -force -name {self._process_name}")
        _wait_until(lambda: not self.status_service, 20)

    def restart_service(self):
        """Restart the service.
        """
        self._log.info("Restarting service %s", self._service_name)
        self.session.run_ps(f"Restart-Service {self._service_name}")
        _wait_until(self.status_service, 20)

    def remove_remote_server_nodes(self) -> bool:
        """Remove the RemoteServerNodes folder from the vsmGadgetServer.store file.

        This method:
        1. Stops the VSM GadgetServer service
        2. Opens the store file (ZIP format) directly for modification
        3. Removes any RemoteServerNodes entries if they exist
        4. Properly disposes of file handles to prevent locking
        5. Always restarts the service at the end

        Returns:
            bool: True if successful, False if any error occurs
        """
        store_file_path = rf"{self._data_dir}\vsmGadgetServer.store"
        backup_file = rf"{self._data_dir}\vsmGadgetServer.store.backup_{int(time.time())}"

        self._log.info("Starting RemoteServerNodes removal from %s", store_file_path)

        # Remember if service was running
        was_running = self.status_service

        try:
            # Stop service if running
            if was_running:
                self._log.info("Stopping service for store file modification")
                self.stop_service()

            # Check if store file exists
            self._log.info("Checking if store file exists")
            result = self.session.run_ps(f"Test-Path '{store_file_path}'")
            if result.std_out.decode('utf-8').strip() != 'True':
                self._log.error("Store file not found: %s", store_file_path)
                return False

            # Create backup of original store file
            self._log.info("Creating backup of original store file")
            result = self.session.run_ps(f"Copy-Item '{store_file_path}' '{backup_file}'")
            if result.status_code != 0:
                self._log.error("Failed to create backup: %s", result.std_err.decode('utf-8'))
                return False

            # Directly manipulate ZIP file to remove RemoteServerNodes entries
            self._log.info("Removing RemoteServerNodes entries from ZIP file")
            remove_entries_cmd = f"""
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            Add-Type -AssemblyName System.IO.Compression

            try {{
                # Open the ZIP file for update
                $zipStream = [System.IO.File]::Open('{store_file_path}', [System.IO.FileMode]::Open)
                $zipArchive = [System.IO.Compression.ZipArchive]::new(
                    $zipStream,
                    [System.IO.Compression.ZipArchiveMode]::Update
                )

                try {{
                    # Find entries that start with "RemoteServerNodes" in the root
                    $entriesToRemove = @()
                    foreach ($entry in $zipArchive.Entries) {{
                        if ($entry.FullName -like "RemoteServerNodes*") {{
                            $entriesToRemove += $entry
                        }}
                    }}

                    # Remove the entries
                    $removedCount = 0
                    foreach ($entry in $entriesToRemove) {{
                        $entry.Delete()
                        $removedCount++
                    }}

                    Write-Output "REMOVED_$removedCount"
                }} finally {{
                    $zipArchive.Dispose()
                    $zipStream.Close()
                    $zipStream.Dispose()
                }}

                Write-Output "SUCCESS"
            }} catch {{
                Write-Error "Failed to remove RemoteServerNodes: $($_.Exception.Message)"
                exit 1
            }}
            """
            result = self.session.run_ps(remove_entries_cmd)
            if result.status_code != 0 or "SUCCESS" not in result.std_out.decode('utf-8'):
                result_err = result.std_err.decode('utf-8')
                self._log.error("Failed to remove RemoteServerNodes from store file: %s", result_err)
                # Restore backup
                self._log.info("Restoring backup file")
                self.session.run_ps(f"Copy-Item '{backup_file}' '{store_file_path}' -Force")
                return False

            # Log how many entries were removed
            output = result.std_out.decode('utf-8')
            if "REMOVED_" in output:
                removed_count = output.split("REMOVED_")[1].split()[0]
                self._log.info("Successfully removed %s RemoteServerNodes entries", removed_count)
            else:
                self._log.info("No RemoteServerNodes entries found to remove")

            # Remove backup file on success
            # self._log.info("Removing backup file")
            # self.session.run_ps(f"Remove-Item '{backup_file}' -Force")

            self._log.info("RemoteServerNodes removal completed successfully")
            return True

        except Exception as e:
            self._log.error("Exception occurred while removing RemoteServerNodes: %s", str(e))
            return False

        finally:
            # Always restart the service at the end
            try:
                if was_running:
                    self._log.info("Restarting service")
                    self.start_service()
                else:
                    self._log.info("Service was not running initially, starting it now")
                    self.start_service()
            except Exception as e:
                self._log.error("Failed to restart service: %s", str(e))
