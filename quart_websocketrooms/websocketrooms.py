from quart import Quart, websocket
import json
import asyncio
from typing import Optional, Callable, List

from .room import Room
from .user import User


class WebSocketRooms(Quart):
    """The room based websocket app"""
    def __init__(
        self,
        import_name: str,
        static_url_path: Optional[str] = None,
        static_folder: Optional[str] = "static",
        static_host: Optional[str] = None,
        host_matching: Optional[bool] = False,
        subdomain_matching: bool = False,
        template_folder: Optional[str] = "templates",
        instance_path: Optional[str] = None,
        instance_relative_config: bool = False,
        root_path: Optional[str] = None,
        #################################
        # Extra arguments for rooms app #
        #################################
        CustomRoomClass: Optional[type] = Room,
        CustomUserClass: Optional[type] = User,
        code_length: Optional[int] = None,
    ) -> None:
        self.rooms = dict()
        self.custom_incoming_steps = []
        self.custom_outgoing_steps = []

        super().__init__(
            import_name,
            static_url_path,
            static_folder,
            static_host,
            host_matching,
            subdomain_matching,
            template_folder,
            instance_path,
            instance_relative_config,
            root_path
        )

        self.Room = CustomRoomClass
        self.User = CustomUserClass
        self.code_length = code_length
        self.default_incoming_steps = [
                self.create_room,
                self.join_room,
                self.load_room,
                self.close_room,
                self.remove_from_room,
                self.save_room,
                self.make_host,
                self.remove_host,
                self.change_host,
        ]
        self.default_outgoing_steps = []

    def websocket_rooms_route(
            self,
            rule: str,
            endpoint: Optional[str] = None,
            view_func: Optional[Callable] = None,
            defaults: Optional[dict] = None,
            host: Optional[str] = None,
            subdomain: Optional[str] = None,
            strict_slashes: Optional[bool] = None,
        ):
        if view_func is None:
            view_func = self.ws_view
        super().add_websocket(
            rule,
            endpoint,
            view_func,
            defaults=defaults,
            host=host,
            subdomain=subdomain,
            strict_slashes=strict_slashes,
        )
    async def ws_view(self):
        user = self.User()

        send = asyncio.create_task(self.send_messages(user))
        recieve = asyncio.create_task(self.recieve_messages(websocket, user))
        try:
            await asyncio.gather(send, recieve)
        except asyncio.CancelledError:
            await self.cancelled(user)
            raise

    async def cancelled(self, user):
        print("Connection dropped", flush=True)
        if user.room is not None:
            print("User was in room " + user.room.code, flush=True)
            code = user.room.code
            if await user.room.remove_user(user):
                del self.rooms[code]
                print("There " + ("are" if len(self.rooms) != 1 else "is") + " now {0} room".format(len(self.rooms)) + ("s" if len(self.rooms) != 1 else ""), flush=True)

    async def send_messages(self, user):
        while True:
            message = await user.queue.get()
            
            for process in self.default_outgoing_steps:
                await process(user, message)
            
            for process in self.custom_outgoing_steps:
                await process(user, message)

            await websocket.send(json.dumps(message))

    async def recieve_messages(self, websocket, user):
        while True:
            raw_data = await websocket.receive()
            message = json.loads(raw_data)

            # Built in handling
            for process in self.default_incoming_steps:
                await process(user, message)

            # Custom Processing
            for process in self.custom_incoming_steps:
                await process(user, message)
        
    def incoming_processing_step(self, func):
        self.custom_incoming_steps.append(func)
        return func
    
    def outgoing_processing_step(self, func):
        self.custom_outgoing_steps.append(func)
        return func

    def allocate_room(self):
        room = self.Room(list(self.rooms), self.code_length)
        self.rooms[room.code] = room
        return room
        
    async def create_room(self, user, message) -> None:
        if message["type"] == "create_room":
            user.username = message["username"]
            user.host = True
            room = self.allocate_room()
            room.loaded = False

            room.add_user(user)
            
            print("There " + ("are" if len(self.rooms) != 1 else "is") + " now {0} room".format(len(self.rooms)) + ("s" if len(self.rooms) != 1 else ""), flush=True)
            await user.queue.put({"type": "create_room", "room_code": room.code})
            await user.room.send_users_update()

    async def join_room(self, user, message) -> None:
        if message["type"] == "join_room":
            user.username = message["username"]
            code = message["code"]
            join_response = {"type": "join_room"}
            fail_reason = ""
            if code in self.rooms:
                room = self.rooms[code]
                if room.add_user(user):
                    join_response["success"] = True
                    pass
                else:
                    join_response["success"] = False
                    join_response["fail_reason"] = "username taken"
            else:
                join_response["success"] = False
                join_response["fail_reason"] = "invalid code"

            await user.queue.put(join_response)
            if join_response["success"]:
                await user.room.send_users_update()

    async def load_room(self, user, message) -> None:
        if message["type"] == "load_room":
            user.username = message["username"]
            user.host = True
            room = self.allocate_room()
            room.add_user(user)
            save_data = message["save_data"]
            print("save_data: {}".format(save_data), flush=True)
            room.load_from_save(save_data)
            
            print("There " + ("are" if len(self.rooms) != 1 else "is") + " now {0} room".format(len(self.rooms)) + ("s" if len(self.rooms) != 1 else ""), flush=True)
            await user.queue.put({"type": "load_room", "room_code": room.code})
            await user.room.send_users_update()

    async def close_room(self, user, message) -> None:
        if (
            message["type"] == "close_room"
            and user.host
            and user.room.code in self.rooms
        ):
            code = user.room.code

            await user.room.broadcast({"type": "room_closed"})
            del self.rooms[code]
            print("There " + ("are" if len(self.rooms) != 1 else "is") + " now {0} room".format(len(self.rooms)) + ("s" if len(self.rooms) != 1 else ""), flush=True)
    
    async def remove_from_room(self, user, message) -> None:
        if (
            (
                message["type"] == "leave_room"
                or (message["type"] == "remove_from_room" and message["username"] in user.room.users)
            )
            and user.room.code in self.rooms
        ):
            code = user.room.code

            user_to_remove = user.room.users[message["username"] if message["type"] == "remove_from_room" else user.username]
            delete_room = await user.room.remove_user(user_to_remove)
            await user_to_remove.queue.put({"type": "removed_from_room", "username": user_to_remove.username})

            if delete_room:
                del self.rooms[code]
                print("There " + ("are" if len(self.rooms) != 1 else "is") + " now {0} room".format(len(self.rooms)) + ("s" if len(self.rooms) != 1 else ""), flush=True)

    async def save_room(self, user, message) -> None:
        if message["type"] == "save_room":
            await user.queue.put({"type": "save_room", "save_data": user.room.save_room()})

    async def make_host(self, user, message) -> None:
        if message["type"] == "make_host" and user.host:
            user_to_promote = user.room.users[message["username"]]
            await user.room.make_host(user_to_promote)

    async def remove_host(self, user, message) -> None:
        if message["type"] == "remove_host" and user.host:
            await user.room.remove_host(user)

    async def change_host(self, user, message) -> None:
        if message["type"] == "change_host" and user.host:
            user_to_promote = user.room.users[message["username"]]
            if not user_to_promote.host:
                await user.room.make_host(user_to_promote)
                await user.room.remove_host(user)

