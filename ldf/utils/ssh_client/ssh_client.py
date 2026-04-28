import logging

import paramiko

log = logging.getLogger(__name__)


class SSHClient:

    def __init__(
        self,
        host: str = None,
        username: str = None,
        password: str = None,
        port=22,
        key_filename: str = None,
        timeout=10
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.key_filename = key_filename
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.timeout = timeout

    def connect(self):

        if not self.host or not self.username:
            log.error("Failed SSH: host and username are required")
            return
        if not (self.password or self.key_filename):
            log.error("Failed SSH: Either password or key_filename must be provided")
            return

        self.client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            key_filename=self.key_filename,
            timeout=self.timeout
        )
        log.info(f"SSH connection established to host {self.host}")

    def command(self, cmd: str, sudo=True) -> str | bool:

        if not self.client.get_transport():
            log.error("Must call SSHClient.connect before issuing commands")
            return

        if sudo:
            cmd = f"sudo -S -p '' {cmd}"
        stdin, stdout, stderr = self.client.exec_command(cmd)
        if sudo:
            stdin.write(self.password + "\n")

        output = stdout.read().decode()
        error = stderr.read().decode()
        exit_status = stdout.channel.recv_exit_status()

        if not exit_status:
            return output
        else:
            log.error(error)
            return False

    def close(self):
        if self.client:
            self.client.close()
            log.info(f"SSH connection closed from host {self.host}")
