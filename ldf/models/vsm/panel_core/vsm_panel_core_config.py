
class PanelCoreConfig:
    name: str
    host: str
    port: int
    protocol: str
    username: str
    password: str

    def __init__(self, name: str, host: str, port: int, protocol: str, username: str, password: str):
        self.name = name
        self.host = host
        self.port = port
        self.protocol = protocol
        self.username = username
        self.password = password
