from asyncio import run, sleep
from pathlib import Path

from ldf.models.powercore.telnet import Telnet, TelnetConfig

try:
    """try reading credentials from file"""
    creds_file = Path(__file__).parent / '../../../.telnet'
    creds_file = creds_file.resolve()
    with open(creds_file, "r") as tn_creds:
        c = tn_creds.read().strip()

        tn_user, tn_pw = c.split(":")[:2]

except Exception:
    print(
        f"expecting telnet credentials 'user:pass' in {creds_file.absolute()}"
    )
    exit(1)


async def main():

    async with Telnet(
        TelnetConfig(
            host="192.168.101.240",
            user=tn_user,
            passwd=tn_pw,
        )
    ) as tn:

        print("sending coldstart")
        await tn.coldstart()
        print("coldstart done")

        while True:
            print(await tn.cpu_usage("desc", 10))
            await sleep(0.5)


if __name__ == "__main__":
    try:
        run(main())
    except KeyboardInterrupt:
        pass
