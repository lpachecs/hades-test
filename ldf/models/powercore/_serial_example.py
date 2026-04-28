from asyncio import run

from ldf.models.powercore.serial_connection import SerialConnection


async def main():
    async with SerialConnection() as serial:
        print("serial logs:")
        async for line in serial.lines():
            print(line)

if __name__ == "__main__":
    try:
        run(main())
    except KeyboardInterrupt:
        pass
