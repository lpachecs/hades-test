import asyncio
from typing import Callable, Coroutine

from datamodel.client.client import Client


def create_nats_client(home_addrs: list[str]) -> Client:
    """Create and return a datamodel.client.Client connected to the provided NATS addresses.

    Args:
        home_addrs (list[str]): List of NATS server addresses.
    Returns:
        Client: A connected datamodel.client.Client instance.
    """
    return Client(home_addrs)


async def subscribe_for_updates(
    client: Client,
    subs: list[tuple[str, Callable]],
    event: asyncio.Event | None = None,
) -> list[asyncio.Task[Coroutine]]:
    """Subscribe to multiple NATs subjects for updates using apropriate callback functions

    Args:
        client (client.Client): datamodel.client object used to connect to NATs broker
        subs (list[tuple[str, Coroutine]]): Address + Handler pairings for device model updates

    Returns:
        list[Coroutine]: References to subscription tasks
    """

    async with client:
        subscriptions = [asyncio.create_task(client.sub(sub, cb)) for sub, cb in subs]
        for task in subscriptions:
            await task

    return subscriptions
