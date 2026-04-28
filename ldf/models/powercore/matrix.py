from enum import Enum
from typing import cast

from ember_py import CondensedMatrix, ConnectionAlreadyExistsError, EmberClient


class Matrix:
    _client: EmberClient

    _base_path = "1.3.1"

    def __init__(self, client: EmberClient, base_path: str | None = None):
        self._client = client
        if base_path is not None:
            self._base_path = base_path

    async def connect(self, source: Enum | int, target: Enum | int, ignore_already_connected=False):
        """connect() expects source and target from an enum

        example:
            class Foo(Enum):
                Source01 = 1650
                Target01 = 1630

            matrix.connect(Foo.Source01, Foo.Target01)
        """
        s_val = source.value if isinstance(source, Enum) else source
        t_val = target.value if isinstance(target, Enum) else target
        try:
            await self._client.set(
                self._base_path,
                f"{s_val}>{t_val}",
                # force=True,
            )
        except ConnectionAlreadyExistsError as e:
            if ignore_already_connected:
                pass
            else:
                raise e

    @property
    async def ember_matrix(self) -> CondensedMatrix:
        return cast(CondensedMatrix, await self._client.get(self._base_path))
