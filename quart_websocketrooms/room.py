from typing import (
    Optional,
    List
)
import random
import string


class Room():
    def __init__(self, existing_codes: Optional[List[str]] = [], code_length: Optional[int] = 8) -> None:
        self.code = self.generate_code(existing_codes, code_length if code_length is not None else 8)
        self.users = {}
        self.hosts = {}
        self.loaded = False
    
    def load_from_save(self, save_data: dict) -> None:
        self.loaded = True
        self.save_data = save_data
        for key in save_data:
            if key not in ["users", "hosts"]:
                setattr(self, key, save_data[key])
    
    def save_room(self) -> dict:
        save_data = {"users": list(self.users), "hosts": list(self.hosts)}
        self.save_data = save_data
        return save_data
    
    async def broadcast(self, message: dict) -> None:
        for username in self.users:
            await self.users[username].queue.put(message)
    
    async def send_to_hosts(self, message: dict) -> None:
        for username in self.hosts:
            await self.hosts[username].queue.put(message)

    def generate_code(self, existing_codes: List[str], code_length: int) -> str:
        code = "".join(random.choices(string.ascii_letters + string.digits, k=code_length))
        while code in existing_codes:
            code = "".join(random.choices(string.ascii_letters + string.digits, k=code_length))

        return code
    
    def add_user(self, user) -> bool:
        if user.username not in self.users:
            self.users[user.username] = user
            user.room = self
            if user.host:
                self.hosts[user.username] = user
            return True
        else:
            return False

    async def remove_user(self, user) -> bool:
        del self.users[user.username]
        user.room = None
        await self.remove_host(user)
        await self.broadcast({"type": "removed_from_room", "username": user.username})
        await self.send_users_update()

        return len(self.users) == 0

    async def make_host(self, user = None) -> None:
        # if no user specified, find first non host to promote
        if user is None:
            for username in self.users:
                if username not in self.hosts:
                    user = self.users[username]
                    break

        user.host = True
        self.hosts[user.username] = user
        await self.send_hosts_update(added_user=user)

    async def remove_host(self, user) -> None:
        if user.username in self.hosts:
            if len(self.hosts) == 1 and len(self.users) != 0:
                await self.make_host()
            del self.hosts[user.username]
            user.host = False
            await self.send_hosts_update(removed_user=user)

    async def send_users_update(self) -> None:
        await self.broadcast({"type": "users_update", "users": {username: {"host": self.users[username].host} for username in self.users}})

    async def send_hosts_update(self, added_user=None, removed_user=None):
        if added_user is not None:
            await added_user.queue.put({"type": "host_promotion"})
            await self.broadcast({"type": "hosts_update", "added": added_user.username})
        else:
            await self.broadcast({"type": "hosts_update", "removed": removed_user.username})
