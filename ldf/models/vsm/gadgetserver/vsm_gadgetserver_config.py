"""Configuration class for the VSM Gadgetserver.
"""


class GadgetServerConfig:
    """Gadgetserver class to store the name and address of the server.

    ! This is only used for test configuration !
    """
    def __init__(self, name: str, address: str):
        self.name = name
        self.address = address


class GadgetServerConfigNet1:
    """Gadgetserver class to store the name and address of the server.

    ! This is only used for test configuration !
    """
    def __init__(self, name: str):
        self.name = name
