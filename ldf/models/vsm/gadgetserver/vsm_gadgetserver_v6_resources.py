"""Resources for VSM GadgetServer v6 REST API."""

import json
from typing import List, Optional


class SingleOption:
    """Represents a single option with name and value."""

    def __init__(
            self,
            name: Optional[str] = None,
            value_as_string: Optional[str] = None,
            dictionary: Optional[dict] = None
    ):
        self.name = name if name is not None else ""
        self.value_as_string = value_as_string if value_as_string is not None else ""

        if dictionary:
            self.from_dict(dictionary)

    def from_dict(self, obj: dict) -> None:
        self.name = obj.get("name", "")
        self.value_as_string = obj.get("valueAsString", "")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "valueAsString": self.value_as_string
        }


class VectorOption:
    """Represents a multi-value option with name and multiple values."""

    def __init__(
            self,
            name: Optional[str] = None,
            values_as_strings: Optional[List[str]] = None,
            dictionary: Optional[dict] = None
    ):
        self.name = name if name is not None else ""
        self.values_as_strings = values_as_strings if values_as_strings is not None else []

        if dictionary:
            self.from_dict(dictionary)

    def from_dict(self, obj: dict) -> None:
        self.name = obj.get("name", "")
        self.values_as_strings = obj.get("valuesAsStrings", [])

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "valuesAsStrings": self.values_as_strings
        }


class UdpConfiguration:
    """UDP configuration for protocol settings."""

    def __init__(self, override_rx_port: int = 0, override_tx_port: int = 0, flags: int = 0,
                 broadcast_address: Optional[str] = None, dictionary: Optional[dict] = None):
        self.override_rx_port = override_rx_port
        self.override_tx_port = override_tx_port
        self.flags = flags
        self.broadcast_address = broadcast_address if broadcast_address is not None else ""

        if dictionary:
            self.from_dict(dictionary)

    def from_dict(self, obj: dict) -> None:
        self.override_rx_port = obj.get("overrideRxPort", 0)
        self.override_tx_port = obj.get("overrideTxPort", 0)
        self.flags = obj.get("flags", 0)
        self.broadcast_address = obj.get("broadcastAddress", "")

    def to_dict(self) -> dict:
        return {
            "overrideRxPort": self.override_rx_port,
            "overrideTxPort": self.override_tx_port,
            "flags": self.flags,
            "broadcastAddress": self.broadcast_address
        }


class ProtocolMapping:
    """Represents a protocol mapping with key and handle."""

    def __init__(self, key: Optional[str] = None, handle: Optional[str] = None, dictionary: Optional[dict] = None):
        self.key = key if key is not None else ""
        self.handle = handle if handle is not None else ""

        if dictionary:
            self.from_dict(dictionary)

    def from_dict(self, obj: dict) -> None:
        self.key = obj.get("key", "")
        self.handle = obj.get("handle", "")

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "handle": self.handle
        }


class ProtocolTableContract:
    """Represents protocol table/driver mapping contract."""

    def __init__(self, mappings: Optional[List[ProtocolMapping]] = None, dictionary: Optional[dict] = None):
        self.mappings = mappings if mappings is not None else []

        if dictionary:
            self.from_dict(dictionary)

    def from_dict(self, obj: dict) -> None:
        if "mappings" in obj:
            self.mappings = [ProtocolMapping(dictionary=mapping) for mapping in obj["mappings"]]

    def to_dict(self) -> dict:
        return {
            "mappings": [mapping.to_dict() for mapping in self.mappings]
        }


class ProtocolSettings:
    """Protocol settings for VSM GadgetServer v6 REST API."""

    def __init__(
        self,
        single_value_options: Optional[List[SingleOption]] = None,
        multi_value_options: Optional[List[VectorOption]] = None,
        active_address: Optional[str] = None,
        address_collection: Optional[List[str]] = None,
        binding_interface: Optional[str] = None,
        udp_configuration: Optional[UdpConfiguration] = None,
        display_name: Optional[str] = None,
        stream_type: int = 0,
        driver_mapping: Optional[ProtocolTableContract] = None,
        is_enabled: bool = True,
        dictionary: Optional[dict] = None
    ):
        self.single_value_options = single_value_options if single_value_options is not None else []
        self.multi_value_options = multi_value_options if multi_value_options is not None else []
        self.active_address = active_address if active_address is not None else ""
        self.address_collection = address_collection if address_collection is not None else []
        self.binding_interface = binding_interface if binding_interface is not None else ""
        self.udp_configuration = udp_configuration
        self.display_name = display_name if display_name is not None else ""
        self.stream_type = stream_type
        self.driver_mapping = driver_mapping if driver_mapping is not None else ProtocolTableContract()
        self.is_enabled = is_enabled

        if dictionary:
            self.from_dict(dictionary)

    def from_dict(self, obj: dict) -> None:
        """Load settings from dictionary (API response)."""
        if "singleValueOptions" in obj:
            self.single_value_options = [SingleOption(dictionary=opt) for opt in obj["singleValueOptions"]]
        if "multiValueOptions" in obj:
            self.multi_value_options = [VectorOption(dictionary=opt) for opt in obj["multiValueOptions"]]

        self.active_address = obj.get("activeAddress", "")
        self.address_collection = obj.get("addressCollection", [])
        self.binding_interface = obj.get("bindinInterface", "")  # Note: API has typo 'bindinInterface'
        self.display_name = obj.get("displayName", "")
        self.stream_type = obj.get("streamType", 0)
        self.is_enabled = obj.get("isEnabled", True)

        if "udpConfiguration" in obj and obj["udpConfiguration"] is not None:
            self.udp_configuration = UdpConfiguration(dictionary=obj["udpConfiguration"])

        if "DriverMapping" in obj:
            self.driver_mapping = ProtocolTableContract(dictionary=obj["DriverMapping"])

    def to_dict(self) -> dict:
        """Convert settings to dictionary for API requests."""
        result = {
            "singleValueOptions": [opt.to_dict() for opt in self.single_value_options],
            "multiValueOptions": [opt.to_dict() for opt in self.multi_value_options],
            "activeAddress": self.active_address,
            "addressCollection": self.address_collection,
            "bindinInterface": self.binding_interface,  # Note: API expects 'bindinInterface'
            "displayName": self.display_name,
            "streamType": self.stream_type,
            "DriverMapping": self.driver_mapping.to_dict(),
            "isEnabled": self.is_enabled
        }

        if self.udp_configuration is not None:
            result["udpConfiguration"] = self.udp_configuration.to_dict()
        else:
            result["udpConfiguration"] = None

        return result

    def add_single_option(self, name: str, value: str) -> None:
        """Add a single value option."""
        self.single_value_options.append(SingleOption(name, value))

    def add_multi_option(self, name: str, values: List[str]) -> None:
        """Add a multi-value option."""
        self.multi_value_options.append(VectorOption(name, values))

    def add_driver_mapping(self, key: str, handle: Optional[str] = None) -> None:
        """Add a driver mapping. If handle is not provided, it will be set later by ProtocolContract."""
        self.driver_mapping.mappings.append(ProtocolMapping(key, handle or ""))


class ProtocolContract:
    """Complete protocol contract for v6 API."""

    def __init__(
        self,
        protocol_id: Optional[str] = None,
        factory_id: Optional[str] = None,
        settings: Optional[ProtocolSettings] = None,
        dictionary: Optional[dict] = None
    ):
        self.factory_id = factory_id if factory_id is not None else ""

        # If no protocol_id is given, use factory_id as the protocol_id
        if protocol_id is None and factory_id is not None:
            self.protocol_id = factory_id
        else:
            self.protocol_id = protocol_id if protocol_id is not None else ""

        self.settings = settings if settings is not None else ProtocolSettings()

        # Track if this is loaded from existing data
        self._loaded_from_dict = False

        if dictionary:
            self.from_dict(dictionary)
            self._loaded_from_dict = True
        else:
            # Only update driver mapping handles for new protocols, not existing ones
            self._update_driver_mapping_handles()

    def _update_driver_mapping_handles(self):
        """Update all driver mapping handles to use the protocol ID."""
        for mapping in self.settings.driver_mapping.mappings:
            mapping.handle = self.protocol_id  # Always set handle to protocol ID

    def from_dict(self, obj: dict) -> None:
        """Load protocol from dictionary (API response)."""
        self.protocol_id = obj.get("id", "")
        self.factory_id = obj.get("factoryId", "")

        if "settings" in obj:
            self.settings = ProtocolSettings(dictionary=obj["settings"])

    def to_dict(self) -> dict:
        """Convert protocol to dictionary for API requests."""
        # Only update handles for new protocols, preserve existing handles for loaded protocols
        if not self._loaded_from_dict:
            self._update_driver_mapping_handles()

        result = {
            "id": self.protocol_id,
            "factoryId": self.factory_id,
            "settings": self.settings.to_dict()
        }

        return result

    def to_json(self) -> str:
        """Convert protocol to JSON string for API requests."""
        return json.dumps(self.to_dict())
