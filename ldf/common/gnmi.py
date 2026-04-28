import logging
from typing import Any, Dict, List, Optional

from pygnmi.client import gNMIclient


class OpenConfigClient:
    def __init__(self, ip: str, port: int, username: str, password: str, insecure: bool = True) -> None:
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.insecure = insecure
        self.client = gNMIclient(
            target=(self.ip, self.port),
            username=self.username,
            password=self.password,
            insecure=self.insecure
        )
        self.log = logging.getLogger(__name__)
        self.log.info(f"Created OpenConfig client: {self.ip}:{self.port}")

    def __enter__(self):
        return self.client

    def __exit__(self, exc_type, exc_value, traceback):
        # self.client.close()
        pass

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        if self.client:
            self.client.close()
            self.client = None

    def get(self, paths: List[str]) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("Client is not connected")
        response = self.client.get(path=paths)
        return response

    def set(self, updates: Dict[str, Any]) -> None:
        if not self.client:
            raise RuntimeError("Client is not connected")
        self.client.set(updates)

    # TODO: Validate functionalty and implement
    def subscribe(self, paths: List[str], callback: Optional[callable] = None) -> None:
        if not self.client:
            raise RuntimeError("Client is not connected")
        self.client.subscribe(paths, callback)
