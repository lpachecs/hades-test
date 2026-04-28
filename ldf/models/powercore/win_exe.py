from logging import getLogger
from subprocess import run
from sys import platform


class WindowsOnlyError(Exception):
    def __init__(self):
        super().__init__(".exe can only be called on windows platforms")


class WinExe:
    exe = ""
    cwd = "."

    def __init__(self, host):
        self._host = host
        self.logger = getLogger(self.__class__.__name__)

    def _run(self, *args):
        if platform != "win32":
            raise WindowsOnlyError()
        full_args = ["powershell", "-Command", self.exe, *args]
        self.logger.debug(f"calling {full_args}")
        return run(
            full_args,
            capture_output=True,
            text=True,
            cwd=self.cwd,
        )
