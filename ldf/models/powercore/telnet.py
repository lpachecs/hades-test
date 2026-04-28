from asyncio import Future, InvalidStateError, Queue, sleep, timeout
from dataclasses import dataclass
from logging import Logger, getLogger
from typing import Literal

from telnetlib3 import TelnetReader, TelnetWriter, open_connection


@dataclass(kw_only=True, frozen=True)
class TelnetConfig:
    host: str = "192.168.101.240"
    port: int = 23
    user: str
    passwd: str


@dataclass
class CpuThread:
    id: int
    name: str
    seconds: float
    percent: float

    @staticmethod
    def from_line(line: str):
        split = [x.strip() for x in line.split("|")]

        return CpuThread(
            int(split[0], 16),
            split[1],
            float(split[2]),
            float(split[3]),
        )

    def __str__(self):
        return f"{self.name:16} (0x{self.id:0x}): {self.percent:8} %, {self.seconds:12} s"  # noqa


@dataclass(frozen=True)
class CpuUsage:
    threads: list[CpuThread]
    time_since_reset: float

    def __str__(self):
        t_str = '\n'.join(str(x) for x in self.threads)

        return f"Running: {self.time_since_reset} seconds\n{t_str}"


SortValue = Literal["asc", "desc"]


class Telnet:
    _conf: TelnetConfig
    _reader: TelnetReader
    _writer: TelnetWriter
    _log: Logger

    _collecting_answer: bool
    _run: bool

    def __init__(self, conf: TelnetConfig):
        self._conf = conf
        self._log = getLogger(__name__)
        self._messages = Queue[str]()
        self._collecting_answer = False
        self._run = True

    async def __aenter__(self):
        is_connected = Future()

        async def _shell(reader: TelnetReader, writer: TelnetWriter):
            init_done = False
            start_print = False

            while self._run:
                msg = await reader.read(2048)
                if "TLNT" in msg and not start_print:
                    start_print = True
                    self._log.info("connected")

                if not init_done:
                    self._log.info("logging in")
                    writer.write(self._conf.user.strip() + "\r")
                    writer.write(self._conf.passwd.strip() + "\r")

                    await writer.drain()

                    try:
                        is_connected.set_result("")
                    except InvalidStateError as e:
                        self._log.error(e)
                    init_done = True

                    continue

                if start_print:
                    if self._collecting_answer:
                        await self._messages.put(msg)
                    # else:
                    #     self._log.debug(msg)

        self._reader, self._writer = await open_connection(
            self._conf.host,
            self._conf.port,
            shell=_shell
        )

        await is_connected

        """get login response and discard"""
        await self._collect_answer()

        return self

    async def cpu_usage(self, sort: SortValue | None = None, limit: int | None = None) -> CpuUsage:
        resp = await self.issue("cpuuse")

        h_idx = resp.index("CPU USAGE BY THREAD")

        """strip headers"""
        resp = resp[h_idx + 4:-1]

        time_since_reset = resp[-1].split(" ")[-1]

        resp = resp[0:-2]

        threads = [
            CpuThread.from_line(x) for x in resp
        ]

        if sort is not None:
            reverse = sort == "desc"
            threads.sort(key=lambda x: x.percent, reverse=reverse)

        if limit is not None:
            threads = threads[0:limit]

        return CpuUsage(
            threads=threads,
            time_since_reset=time_since_reset,
        )

    async def ember_usage(self) -> list[CpuThread]:
        return [
            x for x in (await self.cpu_usage()).threads
            if x.name[0] == "E"
        ]

    async def issue(self, cmd: str, marker="TLNT"):
        self._writer.write(f"{cmd}\r")
        return await self._collect_answer(marker)

    async def _collect_answer(self, marker="TLNT"):
        self._collecting_answer = True
        collection = ""
        while marker not in collection:
            collection += await self._messages.get()
            self._messages.task_done()

            await sleep(0)

        self._collecting_answer = False

        return [x.strip() for x in collection.split("\n")[0:-1]]

    async def coldstart(self):
        self._log.info("sending coldstart to powercore")

        await self.issue("sys_cs", "YES")
        self._writer.write("YES\r")
        await sleep(10)
        await self._check_reboot()

    async def warmstart(self):
        self._log.info("sending warmstart to powercore")

        await self.issue("sys_ws", "YES")
        self._writer.write("YES\r")
        await sleep(10)
        await self._check_reboot()

    async def _check_reboot(self):
        while True:
            try:
                reader, writer = await open_connection(self._conf.host, 23)
                reader.close()
                writer.close()

                break
            except Exception:
                self._log.debug("powercore is still offline")
                await sleep(2)

        self._log.info("powercore is back")

    async def __aexit__(self, a, b, c):
        self._run = False

        self._writer.close()
        self._reader.close()
        try:
            async with timeout(5):
                if (
                        hasattr(self._writer, "protocol") and
                        self._writer.protocol is not None
                ):
                    await self._writer.protocol.waiter_closed
        except TimeoutError:
            self._log.warning("closed with timeout")
