from typing import (
    Optional,
    List
)
import random
import string


class Room():
    users = {}
    hosts = {}
    loaded = False

    def __init__(self, existing_codes: Optional[List[str]] = [], code_length: Optional[int] = 8) -> None:
        self.code = self.generate_code(existing_codes, code_length if code_length is not None else 8)
    
    def load_from_save(self, save_data: dict) -> None:
        self.loaded = True
        for key in save_data:
            self[key] = save_data[key]
    
    def save_room(self) -> dict:
        save_data = {"users": users, "hosts": hosts}
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

        return len(self.users) == 0

    async def make_host(self, user = None) -> None:
        # if no user specified, find first non host to promote
        if user is None:
            for username in self.users:
                if username not in self.hosts:
                    user = self.users[username]
                    break

        user.host = True
        self.hosts[user.username]= user
        await self.broadcast({"type": "hosts_update", "added": user.username})

    async def remove_host(self, user) -> None:
        if user.username in self.hosts:
            if len(self.hosts) == 1 and len(self.users) != 0:
                await self.make_host()
            del self.hosts[user.username]
            user.host = False
            await self.broadcast({"type": "hosts_update", "removed": user.username})


