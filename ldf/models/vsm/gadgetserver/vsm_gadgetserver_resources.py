import json
import time
from abc import ABC, abstractmethod
from enum import Enum, IntEnum
from typing import List, Optional


class ResourceType(IntEnum):
    """Resource type identifiers. Defined by the VSM API."""

    NO_TYPE = 0x0000
    PROTOCOL = 0x0001
    PROTOCOLFACTORY = 0x0002
    DISCARDEDASSEMBLY = 0x0004
    SERVERNODE = 0x0008
    LOGWRITER = 0x0010
    PLUGIN = 0x0040
    ALL = PROTOCOL | PROTOCOLFACTORY | DISCARDEDASSEMBLY | SERVERNODE | LOGWRITER | PLUGIN


class DataPurpose(Enum):
    """
    Data purpose identifiers to filter data for API operations.
    Sometimes VSM GadgetsServer API requires different data for different operations.
    """

    GET = 0x0000
    SET = 0x0001
    DELETE = 0x0002
    CREATE = 0x0004


class ProtocolOptionType(Enum):
    """A Protocol Option can have different types. Each type has different properties.
    This type is in the API represented by an integer value."""

    STRING = 0
    INT = 1
    FLOAT = 2
    BOOL = 3
    ENUM = 4
    FILE = 5


class ProtocolFactoryType(Enum):
    """A Protocol can be a Consumer or a Provider.
    This type is in the API represented by an integer value."""

    CONSUMER = 0
    PROVIDER = 1


class Resource(ABC):
    """Abstract base class (interface) for all resources.
    Provides basic methods to convert resources to and from dictionaries."""

    @abstractmethod
    def from_dict(self, obj: dict):
        """Converts a dictionary to a resource object.
        Normally used to initialize a resource object form a json response.
        """

    @abstractmethod
    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        """Converts a resource object to a dictionary.
        Normally used to prepare a resource object for a json request.

        Set the purpose to filter the data for different operations.
        The gadgetserver API requires different data for different operations
        like GET, SET or DELETE.
        """


class ResourceTopics(Resource):
    """Abstract base class (interface) for all top-level resources."""

    @abstractmethod
    def put_data_json(self) -> str:
        """Returns a json string to update a resource on the VSM GadgetServer."""


def _add_to_dict(out: dict, key: str, value: str) -> None:
    """Helper function to add a key-value pair to a dictionary if the value is not None."""
    if value is not None:
        out[key] = value


def _add_from_dict(obj: dict, key: str):
    """Helper function to get a value from a dictionary if the key exists."""
    if key in obj:
        return obj[key]
    raise KeyError(f"Key '{key}' not found in dictionary")


class ProtocolLayer(Resource):

    _index: int
    _name: str

    def __init__(self, index: Optional[int] = None, name: Optional[str] = None, dictionary: Optional[dict] = None):
        if index is not None and isinstance(index, int):
            self._index = index
        if name is not None and isinstance(name, str):
            self._name = name

        if dictionary:
            self.from_dict(dictionary)

    @property
    def index(self) -> int:
        return self._index

    @property
    def name(self) -> str:
        return self._name

    def __str__(self) -> str:
        return f"""
                # ------------------------------ Protocol Layer ------------------------------ #
                Index: {self.index}
                Name: {self.name}
                # ---------------------------- Protocol Layer end ---------------------------- #"""

    def from_dict(self, obj: dict) -> None:
        self._index = _add_from_dict(obj, "Index")
        self._name = _add_from_dict(obj, "Name")

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out: dict = {}

        if purpose not in (DataPurpose.SET, DataPurpose.DELETE):
            _add_to_dict(out, "Index", str(self._index))
            _add_to_dict(out, "Name", self._name)

        return out


class ProtocolOptions(Resource):

    _name: str
    _description: str
    _option_type: int
    _flags: int
    _default: bool
    _minimum: int
    _maximum: int
    _regex: str
    _values: List[str]

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        option_type: Optional[int] = None,
        flags: Optional[int] = None,
        default: Optional[bool] = None,
        minimum: Optional[int] = None,
        maximum: Optional[int] = None,
        regex: Optional[str] = None,
        values: Optional[List[str]] = None,
        dictionary: Optional[dict] = None,
    ):
        self._name = name if name is not None else ""
        self._description = description if description is not None else ""
        self._option_type = option_type if option_type is not None else 0
        self._flags = flags if flags is not None else 0
        self._default = default if default is not None else False
        self._minimum = minimum if minimum is not None else 0
        self._maximum = maximum if maximum is not None else 0
        self._regex = regex if regex is not None else ""
        self._values = values if values is not None else []

        if dictionary:
            self.from_dict(dictionary)

    @property
    def name(self) -> str:
        """Name of the option."""
        return self._name

    @property
    def description(self) -> str:
        """Description of the option."""
        return self._description

    @property
    def option_type(self) -> ProtocolOptionType:
        """There are 6 different Option Types in the VSM Gadgetserver.

        Returns:
            ProtocolOptionType: STRING, INT, FLOAT, BOOL, ENUM, FILE
        """
        return ProtocolOptionType(self._option_type)

    @property
    def flags(self):
        # TODO What are flags used for?
        return self._flags

    @property
    def default(self):
        """Represents the default value of the option."""
        return self._default

    @property
    def minimum(self) -> float:
        """Only valid for INT and FLOAT option types."""
        return self._minimum

    @property
    def maximum(self) -> float:
        """Only valid for INT and FLOAT option types."""
        return self._maximum

    @property
    def regex(self) -> str:
        """Only valid for STRING option types."""
        return self._regex

    @property
    def values(self) -> List[str]:
        """Only valid for ENUM option types."""
        return self._values

    def __str__(self) -> str:
        return f"""
            # ----------------------------- Protocol Options ----------------------------- #
            Name: {self.name},
            Description: {self.description},
            Type: {self.option_type},
            Flags: {self.flags},
            Default: {self.default},
            Min: {self.minimum},
            Max: {self.maximum},
            Regex: {self.regex},
            Values: {self.values}
            # --------------------------- Protocol Options end --------------------------- #"""

    def from_dict(self, obj: dict) -> None:
        self._name = _add_from_dict(obj, "Name")
        self._description = _add_from_dict(obj, "Description")
        self._option_type = _add_from_dict(obj, "Type")
        self._flags = _add_from_dict(obj, "Flags")
        self._default = _add_from_dict(obj, "Default")
        self._minimum = _add_from_dict(obj, "Minimum")
        self._maximum = _add_from_dict(obj, "Maximum")
        self._regex = _add_from_dict(obj, "Regex")
        self._values = _add_from_dict(obj, "Values")

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out: dict = {}

        if purpose not in (DataPurpose.SET, DataPurpose.DELETE):
            _add_to_dict(out, "Name", self._name)
            _add_to_dict(out, "Description", self._description)
            _add_to_dict(out, "Type", str(self._option_type))
            _add_to_dict(out, "Flags", str(self._flags))
            _add_to_dict(out, "Default", str(self._default))
            _add_to_dict(out, "Minimum", str(self._minimum))
            _add_to_dict(out, "Maximum", str(self._maximum))
            _add_to_dict(out, "Regex", self._regex)
            _add_to_dict(out, "Values", str(self._values))

        return out


class ProtocolDescriptionStreamType(Enum):
    """
    We have different stream types for the different protocols.
    This Enum value returns the stream type as an integer represented in the API
    """

    VIRTUAL = 0
    SERIAL = 1
    TCP_IP = 2
    UDP = 3
    VOLATILE_TCP_IP = 4
    MULTICAST = 5


class ProtocolDescription(Resource):

    _protocol_type: int
    _protocol_guid: str
    _layers: List[ProtocolLayer]
    _protocol_name: str
    _company_name: str
    _supported_device_names: List[str]
    _stream_type: int
    _options: List[ProtocolOptions]

    def __init__(
        self,
        protocol_type: Optional[int] = None,
        protocol_guid: Optional[str] = None,
        layers: Optional[List[ProtocolLayer]] = None,
        protocol_name: Optional[str] = None,
        company_name: Optional[str] = None,
        supported_device_names: Optional[List[str]] = None,
        stream_type: Optional[int] = None,
        options: Optional[List[ProtocolOptions]] = None,
        port: Optional[int] = None,
        dictionary: Optional[dict] = None,
    ):
        self._protocol_type = protocol_type if protocol_type is not None else 0
        self._protocol_guid = protocol_guid if protocol_guid is not None else ""
        self._layers = layers if layers is not None else []
        self._protocol_name = protocol_name if protocol_name is not None else ""
        self._company_name = company_name if company_name is not None else ""
        self._supported_device_names = supported_device_names if supported_device_names is not None else []
        self._stream_type = stream_type if stream_type is not None else 0
        self._options = options if options is not None else []
        self._port = port if port is not None else 0

        if dictionary:
            self.from_dict(dictionary)

    @property
    def protocol_type(self) -> ProtocolFactoryType:
        return ProtocolFactoryType(self._protocol_type)

    @protocol_type.setter
    def protocol_type(self, value: ProtocolFactoryType):
        self._protocol_type = value.value

    @property
    def protocol_guid(self) -> str:
        return self._protocol_guid

    @property
    def layers(self) -> List[ProtocolLayer]:
        return self._layers

    @property
    def protocol_name(self) -> str:
        return self._protocol_name

    @property
    def company_name(self) -> str:
        return self._company_name

    @property
    def supported_device_names(self) -> List[str]:
        return self._supported_device_names

    @property
    def stream_type(self) -> ProtocolDescriptionStreamType:
        return ProtocolDescriptionStreamType(self._stream_type)

    @stream_type.setter
    def stream_type(self, value: ProtocolDescriptionStreamType):
        self._stream_type = value.value

    @property
    def options(self) -> List[ProtocolOptions]:
        return self._options

    @property
    def port(self) -> int:
        return self._port

    def __str__(self) -> str:
        return f"""
            # --------------------------- Protocol Description --------------------------- #
            Type: {self.protocol_type},
            Guid: {self.protocol_guid},
            Layers: {self.layers},
            Name: {self.protocol_name},
            Company: {self.company_name},
            Supported Devices: {self.supported_device_names},
            Stream Type: {self.stream_type},
            Options: {self.options},
            Port: {self.port}
            # ------------------------- Protocol Description end ------------------------- #"""

    def from_dict(self, obj: dict):
        self._protocol_type = _add_from_dict(obj, "Type")
        self._protocol_guid = _add_from_dict(obj, "ProtocolGuid")
        self._protocol_name = _add_from_dict(obj, "ProtocolName")
        self._company_name = _add_from_dict(obj, "CompanyName")
        self._supported_device_names = _add_from_dict(obj, "SupportedDeviceNames")
        self._stream_type = _add_from_dict(obj, "StreamType")
        self._port = _add_from_dict(obj, "Port")
        if "Layers" in obj:
            self._layers = [ProtocolLayer(dictionary=layer) for layer in obj["Layers"]]
        if "Options" in obj:
            self._options = [ProtocolOptions(dictionary=option) for option in obj["Options"]]

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out: dict = {}

        if purpose not in (DataPurpose.SET, DataPurpose.DELETE):
            _add_to_dict(out, "Type", str(self._protocol_type))
            _add_to_dict(out, "ProtocolGuid", self._protocol_guid)
            _add_to_dict(out, "ProtocolName", self._protocol_name)
            _add_to_dict(out, "CompanyName", self._company_name)
            _add_to_dict(out, "SupportedDeviceNames", str(self._supported_device_names))
            _add_to_dict(out, "StreamType", str(self._stream_type))
            _add_to_dict(out, "Port", str(self._port))

            if self._layers:
                out["Layers"] = [layer.to_dict(purpose) for layer in self._layers]
            if self._options:
                out["Options"] = [option.to_dict(purpose) for option in self._options]

        return out


class ProtocolVersion(Resource):

    _company: str
    _description: str
    _file_name: str
    _major: int
    _minor: int
    _private: int
    _build: int

    def __init__(
        self,
        company: Optional[str] = None,
        description: Optional[str] = None,
        file_name: Optional[str] = None,
        major: Optional[int] = None,
        minor: Optional[int] = None,
        private: Optional[int] = None,
        build: Optional[int] = None,
        dictionary: Optional[dict] = None,
    ):
        self._company = company if company is not None else ""
        self._description = description if description is not None else ""
        self._file_name = file_name if file_name is not None else ""
        self._major = major if major is not None else 0
        self._minor = minor if minor is not None else 0
        self._private = private if private is not None else 0
        self._build = build if build is not None else 0

        if dictionary is not None:
            self.from_dict(dictionary)

    @property
    def company(self) -> str:
        return self._company

    @property
    def description(self) -> str:
        return self._description

    @property
    def file_name(self) -> str:
        return self._file_name

    # TODO Check if they are always int or can be string like "1.4v.nightly"
    @property
    def major(self) -> int:
        return self._major

    @property
    def minor(self) -> int:
        return self._minor

    @property
    def private(self) -> int:
        return self._private

    @property
    def build(self) -> int:
        return self._build

    def __str__(self) -> str:
        return f"""
            # ----------------------------- Protocol Version ----------------------------- #
            Company: {self.company},
            Description: {self.description},
            Filename: {self.file_name},
            Major: {self.major},
            Minor: {self.minor},
            Private: {self.private},
            Build: {self.build}
            # --------------------------- Protocol Version end --------------------------- #"""

    def from_dict(self, obj: dict) -> None:
        self._company = obj["Company"]
        self._description = obj["Description"]
        self._file_name = obj["Filename"]
        self._major = obj["Major"]
        self._minor = obj["Minor"]
        self._private = obj["Private"]
        self._build = obj["Build"]

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out: dict = {}

        if purpose not in (DataPurpose.SET, DataPurpose.DELETE):
            _add_to_dict(out, "Company", self._company)
            _add_to_dict(out, "Description", self._description)
            _add_to_dict(out, "Filename", self._file_name)
            _add_to_dict(out, "Major", str(self._major))
            _add_to_dict(out, "Minor", str(self._minor))
            _add_to_dict(out, "Private", str(self._private))
            _add_to_dict(out, "Build", str(self._build))

        return out


class ProtocolFactory(ResourceTopics):

    _handle: str
    _description: ProtocolDescription
    _version: ProtocolVersion
    _is_initialized: bool

    def __init__(
        self,
        handle: Optional[str] = None,
        description: ProtocolDescription = ProtocolDescription(),
        version: ProtocolVersion = ProtocolVersion(),
        is_initialized: Optional[bool] = None,
        dictionary: Optional[dict] = None,
    ):
        self._handle = handle if handle is not None else ""
        self._description = description
        self._version = version
        self._is_initialized = is_initialized if is_initialized is not None else False

        if dictionary:
            self.from_dict(dictionary)

    @property
    def handle(self) -> str:
        return self._handle

    @property
    def description(self) -> ProtocolDescription:
        return self._description

    @property
    def version(self) -> ProtocolVersion:
        return self._version

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized == "true"

    def __str__(self) -> str:
        return f"""
            # ----------------------------- Protocol Factory ----------------------------- #
            Handle: {self.handle},
            Description: {self.description},
            Version: {self.version},
            Is Initialized: {self.is_initialized}
            # --------------------------- Protocol Factory end --------------------------- #"""

    def from_dict(self, obj: dict):
        self._handle = _add_from_dict(obj, "Handle")
        self._is_initialized = _add_from_dict(obj, "IsInitialized")
        if "Description" in obj:
            self._description = ProtocolDescription(dictionary=obj["Description"])
        if "Version" in obj:
            self._version = ProtocolVersion(dictionary=obj["Version"])

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out: dict = {}

        if purpose not in (DataPurpose.SET, DataPurpose.DELETE):
            _add_to_dict(out, "Handle", self._handle)
            _add_to_dict(out, "IsInitialized", str(self._is_initialized))
            if self._description.to_dict(purpose):
                out["Description"] = self._description.to_dict(purpose)
            if self._version.to_dict(purpose):
                out["Version"] = self._version.to_dict(purpose)

        return out

    def put_data_json(self) -> str:
        return json.dumps(self.to_dict(DataPurpose.SET))


class ProtocolMappingKey:
    def __init__(self, value_as_string: str, value_type: int):
        self._value_as_string = value_as_string
        self._value_type = value_type

    @property
    def value_as_string(self) -> str:
        return self._value_as_string

    # TODO What is the ValueType used for? What are these types?
    @property
    def value_type(self) -> int:
        return self._value_type


class ProtocolMapping(Resource):

    _key: ProtocolMappingKey
    _handle: str

    def __init__(
        self,
        key: Optional[ProtocolMappingKey] = None,
        handle: Optional[str] = None,
        dictionary: Optional[dict] = None
    ):
        self._key = key if key is not None else ProtocolMappingKey(value_as_string="", value_type=0)
        self._handle = handle if handle is not None else ""

        if dictionary:
            self.from_dict(dictionary)

    @property
    def key(self) -> ProtocolMappingKey:
        return self._key

    @property
    def handle(self) -> str:
        return self._handle

    def __str__(self) -> str:
        return f"""
            # -------------------------- Protocol Driver Mapping ------------------------- #
            Key: {self.key},
            Handle: {self.handle}
            # -------------------------- Protocol Driver Mapping ------------------------- #"""

    def from_dict(self, obj: dict) -> None:
        self._handle = _add_from_dict(obj, "Handle")
        if "Key" in obj:
            self._key = ProtocolMappingKey(
                value_as_string=obj["Key"]["ValueAsString"], value_type=obj["Key"]["ValueType"]
            )

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out: dict = {}

        if purpose is not DataPurpose.DELETE:
            _add_to_dict(out, "Handle", self._handle)
            if self._key is not None:
                out["Key"] = {
                    "ValueAsString": self._key.value_as_string,
                    "ValueType": self._key.value_type,
                }

        return out


class ProtocolMappings(Resource):
    def __init__(self, mappings: Optional[list[ProtocolMapping]] = None, dictionary: Optional[dict] = None):
        self._mappings = mappings if mappings is not None else []

        if dictionary is not None:
            self.from_dict(dictionary)

    @property
    def mappings(self) -> List[ProtocolMapping]:
        return self._mappings

    def __str__(self) -> str:
        return f"""
            # -------------------------- Protocol Driver Mapping ------------------------- #
            Mappings: {self.mappings}
            # -------------------------- Protocol Driver Mapping ------------------------- #"""

    def from_dict(self, obj: dict) -> None:
        if len(obj) > 0:
            self._mappings = [ProtocolMapping(dictionary=mapping) for mapping in obj]

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out: dict = {}

        if purpose is not DataPurpose.DELETE:
            if self._mappings:
                out["Mappings"] = [mapping.to_dict(purpose) for mapping in self._mappings]

        return out


class ProtocolDriverMappings(Resource):

    _mappings: ProtocolMappings

    def __init__(self, mappings: Optional[ProtocolMappings] = None, dictionary: Optional[dict] = None):

        self._mappings = mappings if mappings is not None else ProtocolMappings()

        if dictionary is not None:
            self.from_dict(dictionary)

    @property
    def mappings(self) -> ProtocolMappings:
        return self._mappings

    def __str__(self) -> str:
        return f"""
            # -------------------------- Protocol Driver Mapping ------------------------- #
            Mappings: {self.mappings}
            # -------------------------- Protocol Driver Mapping ------------------------- #"""

    def from_dict(self, obj: dict) -> None:
        if "Mappings" in obj:
            self._mappings = ProtocolMappings(dictionary=obj["Mappings"])

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:

        out = {}

        if purpose not in (DataPurpose.SET, DataPurpose.DELETE):
            if self._mappings.to_dict(purpose):
                out["Mappings"] = self._mappings.to_dict(purpose)

        return out


class ProtocolSettings(Resource):

    _single_value_options: dict
    _multi_value_options: dict
    _active_address: str
    _address_collection: List[str] | List[int]
    _binding_interface: str
    _display_name: str
    _stream_type: int
    _driver_mapping: ProtocolDriverMappings
    _is_enabled: bool

    def __init__(
        self,
        single_value_options: Optional[dict] = None,
        multi_value_options: Optional[dict] = None,
        active_address: Optional[str] = None,
        address_collection: Optional[List[str] | List[int]] = None,
        binding_interface: Optional[str] = None,
        display_name: Optional[str] = None,
        stream_type: Optional[int] = None,
        driver_mapping: Optional[ProtocolDriverMappings] = None,
        is_enabled: Optional[bool] = None,
        dictionary: Optional[dict] = None,
    ):
        self._single_value_options = single_value_options if single_value_options is not None else {}
        self._multi_value_options = multi_value_options if multi_value_options is not None else {}
        self._active_address = active_address if active_address is not None else ""
        self._address_collection = address_collection if address_collection is not None else []
        self._binding_interface = binding_interface if binding_interface is not None else ""
        self._display_name = display_name if display_name is not None else ""
        self._stream_type = stream_type if stream_type is not None else 0
        self._driver_mapping = driver_mapping if driver_mapping is not None else ProtocolDriverMappings()
        self._is_enabled = is_enabled if is_enabled is not None else False

        if dictionary:
            self.from_dict(dictionary)

    @property
    def single_value_options(self):
        """Single value options are only shown if they are changed.
        They are not shown if they are default."""
        return self._single_value_options

    @property
    def multi_value_options(self):
        """Multi value options are not always shown if they are not changed.
        If they are not shown, they are default."""
        return self._multi_value_options

    @property
    def active_address(self):
        return self._active_address

    @property
    def address_collection(self) -> List[str] | List[int]:
        # A provider has a collection of ports, a consumer has a collection of ip addresses/ Hostnames
        # Check if it is a list of ports (only numbers) or a list
        # of ip addresses/ Hostnames (strings)
        if all(isinstance(item, str) and item.isnumeric() for item in self._address_collection):
            return [int(item) for item in self._address_collection]
        return self._address_collection

    @address_collection.setter
    def address_collection(self, value: List[str] | List[int]):
        if all(isinstance(item, int) for item in value):
            self._address_collection = [str(item) for item in value]
            return
        self._address_collection = value

    @property
    def binding_interface(self) -> str:
        return self._binding_interface

    @property
    def display_name(self) -> str:
        return self._display_name

    @display_name.setter
    def display_name(self, value: str):
        self._display_name = value

    @property
    def stream_type(self):
        return self._stream_type

    @property
    def driver_mapping(self):
        return self._driver_mapping

    @driver_mapping.setter
    def driver_mapping(self, value: ProtocolDriverMappings):
        self._driver_mapping = value

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled == "true"

    def __str__(self) -> str:
        return f"""
            # ----------------------------- Protocol Settings ---------------------------- #
            Single Value Options: {self.single_value_options},
            Multi Value Options: {self.multi_value_options},
            Active Address: {self.active_address},
            Address Collection: {self.address_collection},
            Binding Interface: {self.binding_interface},
            Display Name: {self.display_name},
            Stream Type: {self.stream_type},
            Driver Mapping: {self.driver_mapping},
            Is Enabled: {self.is_enabled}
            # --------------------------- Protocol Settings end -------------------------- #"""

    def from_dict(self, obj):
        self._single_value_options = _add_from_dict(obj, "SingleValueOptions")
        self._multi_value_options = _add_from_dict(obj, "MultiValueOptions")
        self._active_address = _add_from_dict(obj, "ActiveAddress")
        self._address_collection = _add_from_dict(obj, "AddressCollection")
        self._binding_interface = _add_from_dict(obj, "BindingInterface")
        self._display_name = _add_from_dict(obj, "DisplayName")
        self._stream_type = _add_from_dict(obj, "StreamType")
        self._is_enabled = _add_from_dict(obj, "IsEnabled")
        if "DriverMapping" in obj:
            self._driver_mapping = ProtocolDriverMappings(dictionary=obj["DriverMapping"])

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out: dict = {}

        if purpose not in (DataPurpose.SET, DataPurpose.DELETE):
            _add_to_dict(out, "SingleValueOptions", str(self._single_value_options))
            _add_to_dict(out, "MultiValueOptions", str(self._multi_value_options))
            _add_to_dict(out, "ActiveAddress", str(self._active_address))
            _add_to_dict(out, "AddressCollection", str(self._address_collection))
            _add_to_dict(out, "DisplayName", str(self._display_name))
            _add_to_dict(out, "BindingInterface", str(self._binding_interface))
            _add_to_dict(out, "StreamType", str(self._stream_type))
            _add_to_dict(out, "IsEnabled", str(self._is_enabled))
            if self._driver_mapping.to_dict(purpose):
                out["DriverMapping"] = self._driver_mapping.to_dict(purpose)

        return out


class Protocol(ResourceTopics):

    _factory_handle: str
    _holder_operation_state: int
    _protocol_handle: str
    _protocol_operation_state: int
    _settings: ProtocolSettings

    def __init__(
        self,
        factory_handle: Optional[str] = None,
        holder_operation_state: Optional[int] = None,
        protocol_handle: Optional[str] = None,
        protocol_operation_state: Optional[int] = None,
        settings: ProtocolSettings = ProtocolSettings(),
        dictionary: Optional[dict] = None,
    ):
        self._factory_handle = factory_handle if factory_handle is not None else ""
        self._holder_operation_state = holder_operation_state if holder_operation_state is not None else 0
        self._protocol_handle = protocol_handle if protocol_handle is not None else ""
        self._protocol_operation_state = protocol_operation_state if protocol_operation_state is not None else 0
        self._settings = settings

        if dictionary is not None:
            self.from_dict(dictionary)

    @property
    def factory_handle(self):
        return self._factory_handle

    @property
    def holder_operation_state(self):
        return self._holder_operation_state

    @property
    def protocol_handle(self):
        return self._protocol_handle

    @property
    def protocol_operation_state(self):
        return self._protocol_operation_state

    @property
    def settings(self):
        return self._settings

    def __str__(self) -> str:
        return f"""
            # --------------------------------- Protocol --------------------------------- #
            Factory Handle: {self.factory_handle},
            Holder Operation State: {self.holder_operation_state},
            Protocol Handle: {self.protocol_handle},
            Protocol Operation State: {self.protocol_operation_state},
            Settings: {self.settings}
            # ------------------------------- Protocol end ------------------------------- #"""

    def from_dict(self, obj: dict):
        self._factory_handle = _add_from_dict(obj, "FactoryHandle")
        self._holder_operation_state = _add_from_dict(obj, "HolderOperationState")
        self._protocol_handle = _add_from_dict(obj, "ProtocolHandle")
        self._protocol_operation_state = _add_from_dict(obj, "ProtocolOperationState")
        if "Settings" in obj:
            self._settings = ProtocolSettings(dictionary=obj["Settings"])

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out: dict = {}

        if purpose not in (DataPurpose.SET, DataPurpose.DELETE, DataPurpose.CREATE):
            _add_to_dict(out, "HolderOperationState", str(self._holder_operation_state))
            _add_to_dict(out, "ProtocolHandle", str(self._protocol_handle))
            _add_to_dict(out, "ProtocolOperationState", str(self._protocol_operation_state))

        if purpose not in (DataPurpose.SET, DataPurpose.DELETE):
            _add_to_dict(out, "FactoryHandle", str(self._factory_handle))
            if self._settings.to_dict(purpose):
                out["Settings"] = self._settings.to_dict(purpose)

        return out

    def put_data_json(self) -> str:
        payload_dict = {
            "Data": {"Protocols": [self.to_dict(DataPurpose.SET)]},
            "IsUserAction": False,
        }
        return json.dumps(payload_dict)

    def post_data_json(self) -> str:
        payload_dict = {
            "Data": {"Protocols": [self.to_dict(DataPurpose.CREATE)]},
            "IsUserAction": False,
        }
        return json.dumps(payload_dict)


class DiscardedAssembly(ResourceTopics):
    # TODO
    pass


class ServerNodeOptions(Resource):

    _handle: str
    _uri: str
    _location: str
    _comment: str
    _force_single_server: bool
    _joined_servers: List[str]
    _force_primary_server: bool
    _binding: str
    _can_force_primary_server: bool

    def __init__(
        self,
        handle: Optional[str] = None,
        uri: Optional[str] = None,
        location: Optional[str] = None,
        comment: Optional[str] = None,
        force_single_server: Optional[bool] = None,
        joined_servers: Optional[List[str]] = None,
        force_primary_server: Optional[bool] = None,
        binding: Optional[str] = None,
        can_force_primary_server: Optional[bool] = None,
        dictionary: Optional[dict] = None,
    ):
        self._handle = handle if handle is not None else ""
        self._uri = uri if uri is not None else ""
        self._location = location if location is not None else ""
        self._comment = comment if comment is not None else ""
        self._force_single_server = force_single_server if force_single_server is not None else False
        self._joined_servers = joined_servers if joined_servers is not None else []
        self._force_primary_server = force_primary_server if force_primary_server is not None else False
        self._binding = binding if binding is not None else ""
        self._can_force_primary_server = can_force_primary_server if can_force_primary_server is not None else False

        if dictionary is not None:
            self.from_dict(dictionary)

    @property
    def handle(self):
        return self._handle

    @property
    def uri(self):
        return self._uri

    @property
    def location(self) -> str:
        return self._location

    @location.setter
    def location(self, value: str):
        self._location = value

    @property
    def comment(self) -> str:
        return self._comment

    @comment.setter
    def comment(self, value: str):
        self._comment = value

    @property
    def force_single_server(self):
        return self._force_single_server

    @property
    def joined_servers(self):
        return self._joined_servers

    @property
    def force_primary_server(self):
        return self._force_primary_server

    @property
    def binding(self) -> str:
        return self._binding

    # Add tighter validation. Binding for Any or specific IP in addresses
    @binding.setter
    def binding(self, value: str):
        self._binding = value

    @property
    def can_force_primary_server(self) -> bool:
        return self._can_force_primary_server == "true"

    @can_force_primary_server.setter
    def can_force_primary_server(self, value: bool):
        self._can_force_primary_server = value

    def __str__(self) -> str:
        return f"""
            # ---------------------------- Server Node Options --------------------------- #
            Handle: {self.handle},
            Uri: {self.uri},
            Location: {self.location},
            Comment: {self.comment},
            Force Single Server: {self.force_single_server},
            Joined Servers: {self.joined_servers},
            Force Primary Server: {self.force_primary_server},
            Binding: {self.binding},
            Can Force Primary Server: {self.can_force_primary_server}
            # -------------------------- Server Node Options end ------------------------- #"""

    def from_dict(self, obj):
        self._handle = obj["Handle"]
        self._uri = obj["Uri"]
        self._location = obj["Location"]
        self._comment = obj["Comment"]
        self._force_single_server = obj["ForceSingleServer"]
        self._joined_servers = obj["JoinedServers"]
        self._force_primary_server = obj["ForcePrimaryServer"]
        self._binding = obj["Binding"]
        self._can_force_primary_server = obj["CanForcePrimaryServer"]

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out: dict = {}

        _add_to_dict(out, "Location", self._location)
        _add_to_dict(out, "Comment", self._comment)
        _add_to_dict(out, "ForceSingleServer", str(self._force_single_server))
        _add_to_dict(out, "Binding", self._binding)
        _add_to_dict(out, "ForcePrimaryServer", str(self._force_primary_server))

        if purpose not in (DataPurpose.SET, DataPurpose.DELETE):
            _add_to_dict(out, "Handle", self._handle)
            _add_to_dict(out, "Uri", self._uri)
            _add_to_dict(out, "JoinedServers", str(self._joined_servers))  # ! maybe editable ?!
            _add_to_dict(out, "CanForcePrimaryServer", str(self._can_force_primary_server))

        return out


class ServerNodeCaps(Resource):

    _max_allowed_device_controllers: int
    _max_allowed_devices: int

    def __init__(
        self,
        max_allowed_devices: Optional[int] = None,
        max_allowed_device_controllers: Optional[int] = None,
        dictionary: Optional[dict] = None,
    ):
        self._max_allowed_devices = max_allowed_devices if max_allowed_devices is not None else 0
        self._max_allowed_device_controllers = (
            max_allowed_device_controllers
            if max_allowed_device_controllers is not None
            else 0
        )

        if dictionary:
            self.from_dict(dictionary)

    @property
    def max_allowed_devices(self):
        return self._max_allowed_devices

    @property
    def max_allowed_device_controllers(self):
        return self._max_allowed_device_controllers

    def __str__(self) -> str:
        return f"""
            # ----------------------------- Server Node Caps ----------------------------- #
            Max Allowed Devices: {self.max_allowed_devices},
            Max Allowed Device Controllers: {self.max_allowed_device_controllers}
            # --------------------------- Server Node Caps end --------------------------- #"""

    def from_dict(self, obj):
        self._max_allowed_devices = obj["MaxAllowedDevices"]
        self._max_allowed_device_controllers = obj["MaxAllowedDeviceControllers"]

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out = {}

        if purpose not in (DataPurpose.SET, DataPurpose.DELETE):
            if self._max_allowed_devices:
                out["MaxAllowedDevices"] = self._max_allowed_devices
            if self._max_allowed_device_controllers:
                out["MaxAllowedDeviceControllers"] = self._max_allowed_device_controllers

        return out


class ServerNodeLicense(Resource):

    _purpose: int
    _seed: str
    _key: str
    _is_licensed: bool
    _caps: ServerNodeCaps

    def __init__(
        self,
        purpose: Optional[int] = None,
        seed: Optional[str] = None,
        key: Optional[str] = None,
        is_licensed: Optional[bool] = None,
        caps: ServerNodeCaps = ServerNodeCaps(),
        dictionary: Optional[dict] = None,
    ):
        self._purpose = purpose if purpose is not None else 0
        self._seed = seed if seed is not None else ""
        self._key = key if key is not None else ""
        self._is_licensed = is_licensed if is_licensed is not None else False
        self._caps = caps

        if dictionary is not None:
            self.from_dict(dictionary)

    @property
    def purpose(self):
        return self._purpose

    @property
    def seed(self):
        return self._seed

    @property
    def key(self):
        return self._key

    @property
    def is_licensed(self):
        return self._is_licensed

    @property
    def caps(self):
        return self._caps

    def __str__(self) -> str:
        return f"""
            # ---------------------------- Server Node License --------------------------- #
            Purpose: {self.purpose},
            Seed: {self.seed},
            Key: {self.key},
            Is Licensed: {self.is_licensed},
            Caps: {self.caps}
            # -------------------------- Server Node License end ------------------------- #"""

    def from_dict(self, obj):
        self._purpose = obj["Purpose"]
        self._seed = obj["Seed"]
        self._key = obj["Key"]
        self._is_licensed = obj["IsLicensed"]
        self._caps = ServerNodeCaps(dictionary=obj["Caps"])

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out: dict = {}

        if purpose not in (DataPurpose.SET, DataPurpose.DELETE):
            _add_to_dict(out, "Purpose", str(self._purpose))
            _add_to_dict(out, "Seed", str(self._seed))
            _add_to_dict(out, "Key", str(self._key))
            _add_to_dict(out, "IsLicensed", str(self._is_licensed))
            if self._caps.to_dict(purpose):
                out["Caps"] = self._caps.to_dict(purpose)

        return out


class ServerNodeServerNode(Resource):

    _options: ServerNodeOptions
    _machine_name: str
    _version: str
    _startup_time: time.struct_time
    _addresses: List[str]
    _is_local_server: bool
    _operation_state: int
    _node_license: ServerNodeLicense

    def __init__(
        self,
        options: Optional[ServerNodeOptions] = None,
        machine_name: Optional[str] = None,
        version: Optional[str] = None,
        startup_time: Optional[time.struct_time] = None,
        addresses: Optional[List[str]] = None,
        is_local_server: Optional[bool] = None,
        operation_state: Optional[int] = None,
        node_license: Optional[ServerNodeLicense] = None,
        dictionary: Optional[dict] = None,
    ):
        self._options = options if options is not None else ServerNodeOptions()
        self._machine_name = machine_name if machine_name is not None else ""
        self._version = version if version is not None else ""
        self._startup_time = startup_time if startup_time is not None else time.localtime()
        self._addresses = addresses if addresses is not None else []
        self._is_local_server = is_local_server if is_local_server is not None else False
        self._operation_state = operation_state if operation_state is not None else 0
        self._node_license = node_license if node_license is not None else ServerNodeLicense()

        if dictionary is not None:
            self.from_dict(dictionary)

    @property
    def options(self):
        return self._options

    @property
    def machine_name(self):
        return self._machine_name

    @property
    def version(self):
        return self._version

    @property
    def startup_time(self) -> str:
        """Returns Time in a ISO 8601 format."""
        return str(self._startup_time)

    @property
    def addresses(self):
        return self._addresses

    @property
    def is_local_server(self):
        return self._is_local_server

    @property
    def operation_state(self):
        return self._operation_state

    @property
    def node_license(self):
        return self._node_license

    def __str__(self) -> str:
        return f"""
            # -------------------------- Server Node Server Node ------------------------- #
            Options: {self.options},
            Machine Name: {self.machine_name},
            Version: {self.version},
            Startup Time: {self.startup_time},
            addresses: {self.addresses},
            Is Local Server: {self.is_local_server},
            Operation State: {self.operation_state},
            License: {self.node_license}
            # ------------------------ Server Node Server Node end ----------------------- #"""

    def from_dict(self, obj):
        self._options = ServerNodeOptions(dictionary=obj["Options"])
        self._machine_name = obj["MachineName"]
        self._version = obj["Version"]
        self._startup_time = obj["StartupTime"]
        self._addresses = obj["Addresses"]
        self._is_local_server = obj["IsLocalServer"]
        self._operation_state = obj["OperationState"]
        self._node_license = ServerNodeLicense(dictionary=obj["License"])

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out = {}

        if self._options.to_dict(purpose):
            out["Options"] = self.options.to_dict(purpose)
        _add_to_dict(out, "MachineName", self._machine_name)

        if purpose not in (DataPurpose.SET, DataPurpose.DELETE):
            _add_to_dict(out, "Version", self._version)
            _add_to_dict(out, "StartupTime", str(self._startup_time))
            _add_to_dict(out, "Addresses", str(self._addresses))
            _add_to_dict(out, "IsLocalServer", str(self._is_local_server))
            _add_to_dict(out, "OperationState", str(self._operation_state))
            if self._node_license.to_dict(purpose):
                out["License"] = self.node_license.to_dict(purpose)

        return out


class ServerNode(ResourceTopics):

    _handle: str
    _server_node: ServerNodeServerNode

    def __init__(
        self,
        handle: Optional[str] = None,
        server_node: Optional[ServerNodeServerNode] = None,
        dictionary: Optional[dict] = None
    ):
        self._handle = handle if handle is not None else ""
        self._server_node = server_node if server_node is not None else ServerNodeServerNode()

        if dictionary is not None:
            self.from_dict(dictionary)

    @property
    def handle(self):
        return self._handle

    @property
    def server_node(self):
        return self._server_node

    def __str__(self) -> str:
        return f"""
            # -------------------------------- Server Node ------------------------------- #
            Handle: {self.handle},
            Server Node: {self.server_node}
            # ------------------------------ Server Node end ----------------------------- #"""

    def from_dict(self, obj):
        self._handle = obj["Handle"]
        self._server_node = ServerNodeServerNode(dictionary=obj["ServerNode"])

    def to_dict(self, purpose: DataPurpose = DataPurpose.GET) -> dict:
        out: dict = {}

        _add_to_dict(out, "Handle", self._handle)
        if self._server_node.to_dict(purpose):
            out["ServerNode"] = self._server_node.to_dict(purpose)

        return out

    def put_data_json(self) -> str:
        payload_dict = {
            "Data": {"ServerNodes": [self.to_dict(DataPurpose.SET)]},
            "IsUserAction": False,
        }
        return json.dumps(payload_dict)


class LogWriter(ResourceTopics):
    # TODO
    pass


class Plugin(ResourceTopics):
    # TODO
    pass


class ResourceData:

    protocol_factories: List[ProtocolFactory]
    protocols: List[Protocol]
    discarded_assemblies: List[DiscardedAssembly]
    server_nodes: List[ServerNode]
    log_writers: List[LogWriter]
    plugins: List[Plugin]

    def __init__(
        self,
        protocol_factories: Optional[List[ProtocolFactory]] = None,
        protocols: Optional[List[Protocol]] = None,
        discarded_assemblies: Optional[List[DiscardedAssembly]] = None,
        server_nodes: Optional[List[ServerNode]] = None,
        log_writers: Optional[List[LogWriter]] = None,
        plugins: Optional[List[Plugin]] = None,
        dictionary: Optional[dict] = None,
    ):
        protocol_factories = protocol_factories if protocol_factories is not None else []
        self.protocol_factories = protocol_factories
        self.protocols = protocols if protocols is not None else []
        self.discarded_assemblies = discarded_assemblies if discarded_assemblies is not None else []
        self.server_nodes = server_nodes if server_nodes is not None else []
        self.log_writers = log_writers if log_writers is not None else []
        self.plugins = plugins if plugins is not None else []

        if dictionary is not None:
            self.from_dict(dictionary)

    def __str__(self) -> str:
        return f"""
            # ------------------------------- Resource Data ------------------------------ #
            Protocol Factories: {self.protocol_factories},
            Protocols: {self.protocols},
            Discarded Assemblies: {self.discarded_assemblies},
            Server Nodes: {self.server_nodes},
            Log Writers: {self.log_writers},
            Plugins: {self.plugins}
            # ----------------------------- Resource Data end ---------------------------- #"""

    def from_dict(self, obj):
        self.protocol_factories = [
            ProtocolFactory(dictionary=pf) for pf in obj["ProtocolFactories"]
        ]
        self.protocols = [Protocol(dictionary=protocol) for protocol in obj["Protocols"]]
        self.server_nodes = [
            ServerNode(dictionary=server_node) for server_node in obj["ServerNodes"]
        ]
        self.discarded_assemblies = None
        self.log_writers = None
        self.plugins = None

    def to_dict(self, purposes: DataPurpose = DataPurpose.GET) -> dict:
        out = {}

        out["ProtocolFactories"] = [pf.to_dict(purposes) for pf in self.protocol_factories]
        out["Protocols"] = [protocol.to_dict(purposes) for protocol in self.protocols]
        out["ServerNodes"] = [server_node.to_dict(purposes) for server_node in self.server_nodes]
        out["DiscardedAssemblies"] = []
        out["LogWriters"] = []
        out["Plugins"] = []

        return out
