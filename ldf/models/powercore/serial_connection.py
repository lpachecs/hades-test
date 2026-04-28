from asyncio import StreamReader, StreamWriter

from serial_asyncio import open_serial_connection


class SerialConnection:
    _reader: StreamReader
    _writer: StreamWriter

    _connected: bool
    _port: str

    def __init__(self, port="COM4"):
        self._connected = False
        self._port = port

    async def __aenter__(self):
        self._reader, self._writer = await open_serial_connection(
            url=self._port,
            baudrate=115200
        )
        self._connected = True

        return self

    async def __aexit__(self, a, b, c):
        self._connected = False
        self._writer.close()
        await self._writer.wait_closed()

    async def read(self):
        data = await self._reader.readline()
        return data.decode(errors='replace').rstrip()

    async def send(self, message: bytes):
        self._writer.write(message + b'\r\n')
        await self._writer.drain()

    async def lines(self):
        while self._connected:
            yield await self.read()
