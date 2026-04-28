from pathlib import Path
from socket import create_connection, error, timeout
from sys import platform
from time import sleep

from ldf.models.powercore.win_exe import WinExe


class SopExplorer(WinExe):
    exe = "./Sop_Explorer.exe"
    cwd = "C:\\Program Files (x86)\\OnAirDesigner"

    def is_firmware_update_required(self):
        return self._run("-check", "-ip", self._host).returncode == 2

    def update_firmware(self, yes_to_all=False):
        args = ["-update", "-ip", self._host]
        if yes_to_all:
            args.append("-yes")

        return self._run(*args)

    def upload_config(self, path: str | Path):
        self.logger.info(f"uploading {path} to {self._host}")
        if isinstance(path, Path):
            path = path.absolute().as_posix().replace("/", "\\")
        subp = self._run("-config-file-to-unit", path, "-ip", self._host)
        assert subp.returncode == 0

        """wait for the device to shut down"""
        self.logger.info("Waiting for device to shut down ...")

        while self._is_online():
            # self.logger.info("... device still online ...")

            sleep(0.2)

        self.logger.info("... device is offline.")

        self.logger.info("Waiting for device to get back online ...")

        while not self._is_online():
            """wait for the device to come back"""
            sleep(0.2)

        """give it just a little more time"""
        sleep(5)

        self.logger.info("... device is back!")

    def _is_online(self):
        try:
            with create_connection((self._host, 80), timeout=1):
                return True
        except (timeout, error):
            return False

    def have_sops(self):
        if platform != "win32":
            return False

        return (Path(self.cwd) / self.exe).exists()
