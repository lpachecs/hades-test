"""
Device model for the VSM GadgetServer v6 REST API.
"""

import logging
import time
from typing import Any, Optional, Union

import requests
import winrm  # type: ignore
from requests.auth import HTTPBasicAuth

from .vsm_gadgetserver_v6_resources import ProtocolContract

DEFAULT_WINDOWS_SERVICE_NAME = "'vsmGadgetServer 6'"
DEFAULT_WINDOWS_PROCESS_NAME = "vsmGadgetServer"


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


class VsmGadgetServerV6:
    def __init__(
        self,
        address: str,
        username: str,
        password: str,
        port: int = 8303,
        schema: str = "https",
        service_name: str = DEFAULT_WINDOWS_SERVICE_NAME,
        process_name: str = DEFAULT_WINDOWS_PROCESS_NAME
    ):
        self.address = address
        self.username = username
        self.password = password
        self.port = port
        self.schema = schema
        self._log = logging.getLogger(f"{__name__}:{self.address}")
        self.session = requests.Session()
        self.auth = HTTPBasicAuth(username, password)
        self.base_url = f"{self.schema}://{self.address}:{self.port}"
        self.winrm_session = winrm.Session(self.address, auth=(self.username, self.password), transport='ntlm')
        self._service_name = service_name
        self._process_name = process_name

    def _request(self, method: str, endpoint: str, ignore_status_codes: Optional[list] = None, **kwargs) -> Any:
        url = f"{self.base_url}{endpoint}"
        self._log.debug(f"{method.upper()} request to {url}")
        response = self.session.request(method, url, auth=self.auth, verify=False, **kwargs)

        ignore_codes = ignore_status_codes or []
        if not response.ok and response.status_code not in ignore_codes:
            self._log.error(f"Request failed: {response.status_code} {response.text}")
            response.raise_for_status()
        elif response.status_code in ignore_codes:
            self._log.warning(f"Ignoring status code {response.status_code} for {method.upper()} {endpoint}")

        return response.json() if response.text else None

    # New REST API endpoints from Swagger UI
    # Protocols
    def get_protocols(self):
        return self._request("get", "/api/configuration/protocols")

    def get_protocol(self, protocol_id: str):
        return self._request("get", f"/api/configuration/protocols/{protocol_id}")

    def update_protocol(self, protocol_id: str, protocol: Union[ProtocolContract, dict]):
        """Update an existing protocol.

        Args:
            protocol_id: The ID of the protocol to update
            protocol: Can be a ProtocolContract object or a dict (single protocol, not array)

        Returns:
            API response as dict
        """
        if isinstance(protocol, ProtocolContract):
            json_data = protocol.to_dict()
        elif isinstance(protocol, dict):
            json_data = protocol
        else:
            raise ValueError("Protocol must be ProtocolContract or dict (single protocol)")
        return self._request("put", f"/api/configuration/protocols/{protocol_id}", json=json_data)

    def delete_protocol(self, protocol_id: str):
        return self._request("delete", f"/api/configuration/protocols/{protocol_id}")

    # Protocol Factories
    def get_protocol_factories(self):
        return self._request("get", "/api/protocolFactories")

    def create_protocol(self, protocol: Union[ProtocolContract, dict, list]):
        """Create a new protocol.

        Args:
            protocol: Can be a ProtocolContract object, a dict, or a list of protocols

        Returns:
            API response as dict
        """
        if isinstance(protocol, ProtocolContract):
            # Convert ProtocolContract to the expected array format
            json_data = [protocol.to_dict()]
        elif isinstance(protocol, dict):
            # If it's a single protocol dict, wrap it in an array
            json_data = [protocol]
        elif isinstance(protocol, list):
            # If it's already a list, use as is
            json_data = protocol
        else:
            raise ValueError("Protocol must be ProtocolContract, dict, or list")

        return self._request("post", "/api/configuration/protocols", ignore_status_codes=[500], json=json_data)

    # Servers
    def get_servers(self):
        return self._request("get", "/api/servers")

    def get_local_server(self):
        return self._request("get", "/api/servers/local")

    def update_local_server(self, server_json: dict):
        return self._request("put", "/api/servers/local", json=server_json)

    def get_server(self, server_id: str):
        return self._request("get", f"/api/servers/{server_id}")

    def join_server(self, server_ids: list[str]):
        return self._request("post", "/api/servers/join", json=server_ids)

    def unjoin_server(self, server_ids: list[str]):
        return self._request("post", "/api/configuration/servers/unjoin", json=server_ids)

    # ---------------------------------------------------------------------------- #
    #                               WINDOWS SERVICES                              #
    # ---------------------------------------------------------------------------- #

    @property
    def status_service(self) -> bool:
        """Check if the service is running.

        Returns:
            bool: True if the service is running, False otherwise.
        """
        answer = self.winrm_session.run_ps(
            f"(Get-Service {self._service_name}).Status -eq 'Running'"
        ).std_out
        answer = answer.decode("utf-8").strip()
        self._log.info("Service status: %s", answer)
        return answer == "True"

    def start_service(self):
        """Start the service.
        """
        self._log.info("Starting service %s", self._service_name)
        self.winrm_session.run_ps(f"Start-Service {self._service_name}")
        # Wait until service status is up running or timeout
        _wait_until(self.status_service, 30)

    def stop_service(self):
        """Stop the service.
        """
        self._log.info("Stopping service %s", self._service_name)
        self.winrm_session.run_ps(f"Stop-Service {self._service_name}")
        _wait_until(lambda: not self.status_service, 20)

    def kill_service(self):
        """Kill the service.
        """
        self._log.info("Killing service %s", self._service_name)
        self.winrm_session.run_ps(f"Stop-Process -force -name {self._process_name}")
        _wait_until(lambda: not self.status_service, 20)

    def restart_service(self):
        """Restart the service.
        """
        self._log.info("Restarting service %s", self._service_name)
        self.winrm_session.run_ps(f"Stop-Service {self._service_name}")
        _wait_until(lambda: not self.status_service, 20)
        self.winrm_session.run_ps(f"Start-Service {self._service_name}")
        _wait_until(self.status_service, 20)
