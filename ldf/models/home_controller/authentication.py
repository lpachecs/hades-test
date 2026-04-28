
import logging
from datetime import datetime, timedelta

from datamodel.auth import auth_home
from datamodel.auth.auth_pb2 import Operation, Permit, Resource, User
from datamodel.client.client import Client
from google.protobuf import timestamp_pb2


class HomeControllerPermissions:

    def __init__(self):
        self.api_keys = {}
        pass


class HomeControllerPermitOperation:

    def __init__(self, pb: Operation) -> None:
        self.pb = pb
        self.home_id: str = pb.ID
        self.name: str = pb.Name
        self.group: str = pb.Group
        self.kinds: list[str] = pb.ResourceKinds
        self.help: str = pb.Help

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} {self.home_id} {self.name} {self.group} {self.kinds} {self.help}>"


class HomeControllerRolePermit:

    def __init__(self, pb: Permit) -> None:
        self.pb: Permit = pb
        self.resources: list[Resource] = [x for x in pb.Resources]
        self.operation_ids: list[str] = [x for x in pb.OperationIDs]

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} {[(p.Kind, p.Value) for p in self.resources]} {self.operation_ids}>"

    @classmethod
    def create(cls, oper_id: str):

        _ = [Resource(Value="*", Kind="*")]  # Placeholder for adding scope to Permits
        permit = Permit(OperationIDs=[oper_id])
        return cls(permit)


class HomeControllerUserRole:

    def __init__(self, pb):
        self.pb = pb
        self.home_id = pb.ID
        self.label = pb.Label
        self.permits = [HomeControllerRolePermit(permit) for permit in pb.Permits]
        self.inherit = pb.Inherit
        self.desc = pb.Description
        self.last_updated = pb.UpdatedAt

    def __str__(self) -> str:
        formatted_permits = "\n\t".join(str(permit) for permit in self.permits)
        return f"""<{self.__class__.__name__} {self.home_id} {self.label} {self.desc}>
        {formatted_permits}"""


class HomeControllerUser:

    def __init__(self, pb: User, roles: list[HomeControllerUserRole]) -> None:
        self.pb: User = pb
        self.home_id: str = pb.ID
        self.email: str = pb.Email
        self.firstname: str = pb.First
        self.lastname: str = pb.Last
        self.state: str = pb.State
        self.pw_hash: str = pb.Hash
        self.roles: list[HomeControllerUserRole] = roles
        self.last_updated: timestamp_pb2.Timestamp = pb.UpdatedAt

    def __str__(self) -> str:
        formatted_roles = "\n\t".join(str(role) for role in self.roles)
        return f"""<{self.__class__.__name__} {self.firstname} {self.lastname} {self.email}>
        {formatted_roles}>"""

    def set_roles(self, client: Client, role_ids: list[str]):
        return auth_home.auth_set_user_roles(client=client, argid=self.home_id, argRoleIDs=role_ids)

    def recover(self, client: Client):
        return auth_home.auth_get_recover_user(client=client, argid=self.home_id)


class HomeControllerAuthentication:

    def __init__(self, nats_client: Client) -> None:
        self.log = logging.getLogger(__name__)
        self.client = nats_client

    async def _get_status(self):
        return await auth_home.auth_get_status(self.client)

    async def _get_users(self):
        usrs, _ = await auth_home.auth_get_all_users(self.client)
        for usr in usrs:
            yield HomeControllerUser(usr, roles=[
                role async for role in self._get_roles() if role.home_id in usr.RoleIDs
            ])

    async def _get_roles(self):
        roles, _ = await auth_home.auth_get_all_roles(self.client)
        for role in roles:
            yield HomeControllerUserRole(role)

    async def _get_operations(self):
        operations, _ = await auth_home.auth_get_operations(self.client)
        for oper in operations:
            yield HomeControllerPermitOperation(oper)

    @property
    async def users(self):
        async for usr in self._get_users():
            yield usr

    async def filter_users(self, **criteria):
        async for user in self._get_users():
            if all(getattr(user, key, None) == value for key, value in criteria.items()):
                yield user

    async def filter_roles(self, **criteria):
        async for role in self._get_roles():
            if all(getattr(role, key, None) == value for key, value in criteria.items()):
                yield role

    async def create_user(self, email: str, firstname: str, lastname: str, roles: list[str]) -> str:
        user_id, err = await auth_home.auth_create_user(self.client, email, firstname, lastname, roles)
        if not err:
            return user_id
        else:
            raise Exception(err)

    async def delete_user(self, user_id: str) -> bool:
        err = await auth_home.auth_delete_user(self.client, user_id)
        if not err:
            return True
        else:
            raise Exception(err)

    def create_permit(self, permissions: tuple[str, str], oper_ids: list[str]) -> Permit:
        resources = [Resource(Value=resource, kind=kind) for resource, kind in permissions]
        return Permit(Resources=resources, OperationIDs=oper_ids)

    async def create_role(self, label: str, permits: list[Permit], inherit: bool, desc: str):
        role_id, err = await auth_home.auth_create_role(self.client, label, permits, inherit, desc)
        if not err:
            self.log.debug(f"Created new role: {role_id}")
            return role_id
        else:
            raise Exception(err)

    async def remove_role(self, role_id: str) -> bool:
        err = await auth_home.auth_delete_role(self.client, role_id)
        if not err:
            return True
        else:
            return False

    async def create_api_key(self, name: str, role_ids: list[str], lease: int = 7) -> tuple[str, str]:

        now = datetime.now()
        future_date = now + timedelta(days=lease)
        expiry = timestamp_pb2.Timestamp()
        expiry.FromDatetime(future_date)
        key_id, api_key, err = await auth_home.auth_create_api_key(self.client, name, role_ids, expiry)
        if not err:
            self.log.debug(f"Created api key {key_id} for role {role_ids}")
            return key_id, api_key
        else:
            raise Exception(err)

    async def remove_api_key(self, api_key_id: str) -> bool:
        err = await auth_home.auth_delete_api_key(self.client, api_key_id)
        if not err:
            return True
        else:
            return False
