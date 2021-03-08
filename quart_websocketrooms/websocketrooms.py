from quart import Quart, websocket
import random
import string
import json
import asyncio
from typing import Optional, Callable

from .room import Room
from .user import User


class WebSocketRooms(Quart):
    """The room based websocket app"""
    rooms = dict()
    custom_incoming_steps = []
    custom_outgoing_steps = []

    def __init__(
        self,
        import_name: str,
        static_url_path: Optional[str] = None,
        static_folder: Optional[str] = "static",
        static_host: Optional[str] = None,
        host_matching: Optional[bool] = False,
        subdomain_matching: bool = False,
        template_folder: Optional[str] = "templates",
        root_path: Optional[str] = None,
        instance_path: Optional[str] = None,
        instance_relative_config: bool = False,
        #################################
        # Extra arguments for rooms app #
        #################################
        CustomRoomClass: Optional[type] = Room,
        CustomUserClass: Optional[type] = User,
        code_length: Optional[int] = None,
    ) -> None:
        super().__init__(
            import_name,
            static_url_path,
            static_folder,
            static_host,
            host_matching,
            subdomain_matching,
            template_folder,
            root_path,
            instance_path,
            instance_relative_config
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

    def bind_to_route(
            self,
            rule: str,
            endpoint: Optional[str] = None,
            view_func: Optional[Callable] = None,
            defaults: Optional[dict] = None,
            host: Optional[str] = None,
            subdomain: Optional[str] = None,
            *,
            strict_slashes: Optional[bool] = None,
        ):
        super().add_websocket(
            rule,
            endpoint,
            self.ws_view,
            defaults,
            host,
            subdomain,
            strict_slashes,
        )
    async def ws_view():
        user = self.User()

        send = asyncio.create_task(self.send_messagess(user))
        recieve = asyncio.create_task(self.recieve_messages(websocket, user))
        try:
            await asyncio.gather(send, recieve)
        except asyncio.CancelledError:
            await self.cancelled(user)


    async def cancelled(self, user):
        if user.room is not None:
            await user.room.remove_user(user)

    async def send_messages(self, user):
        while True:
            message = await user.queue.get()
            
            for process in self.default_outgoing_steps:
                process(message, user)
            
            for process in self.custom_outgoing_steps:
                process(message, user)

            await websocket.send(json.dumps(message))

    async def recieve_messages(self, websocket, user):
        while True:
            raw_data = await websocket.receive()
            message_type = message["type"]
            message = json.loads(raw_data)
            responses = []

            # Built in handling
            for process in self.default_incoming_steps:
                step_responses = await process(user, message)
                responses += step_responses


            # Custom Processing
            for process in self.custom_incoming_steps:
                steo_responses = await process(user, message)
                responses += step_response

            for response in responses:
                if response is not None:
                    await user.queue.put(response)
        
    async def incoming_processing_step(self):
        def decorator(func: Callable) -> Callable:
            self.custom_incoming_steps.append(func)
            return func
    
    async def outgoing_processing_step(self):
        def decorator(func: Callable) -> Callable:
            self.custom_outgoing_steps.append(func)
            return func

    def allocate_room(self):
        room = Room(list(rooms.keys()), self.code_length)
        self.rooms[room.code] = room
        return room
        
    def create_room(self, user, message) -> dict:
        if message["type"] == "create_room":
            user.username = message["username"]
            user.host = True
            room = allocate_room()
            room.loaded = False

            room.add_user(user)
            
            print("There " + ("are" if len(rooms) != 1 else "is") + " now {0} room".format(len(rooms)) + ("s" if len(rooms) != 1 else ""), flush=True)
            return {"type": "room_created", "room_code": room.code}

    def join_room(self, code, user, username) -> dict:
        if message["type"] == "join_room":
            user.username = username
            response = {"type": "join_room"}
            fail_reason = ""
            if code in rooms:
                if (room.add_user(user)):
                    response["success"] = True
                    pass
                else:
                    response["success"] = False
                    response["fail_reason"] = "username taken"
            else:
                response["success"] = False
                response["fail_reason"] = "invalid code"

            return response;

    def load_room(self, user, username, save_data) -> dict:
        if message["type"] == "load_room":
            room = self.allocate_room(save_data)
            
            print("There " + ("are" if len(rooms) != 1 else "is") + " now {0} room".format(len(rooms)) + ("s" if len(rooms) != 1 else ""), flush=True)
            return {"type": "load_room", "room_code": room.code}

    async def close_room(self, user, message):
        if (
            message["type"] == "close_room"
            and user.host
            and user.room in rooms
        ):

            await user.room.broadcast(code, {"type": "room_closed", "room_code": code})
            del rooms[code]
    
    async def remove_from_room(self, user, message):
        if (
            message["type"] == "remove_from_room"
            and user.room in rooms
        ):
            delete_room = user.room.remove_user(user)

            if delete_room:
                print("There " + ("are" if len(rooms) != 1 else "is") + " now {0} room".format(len(rooms)) + ("s" if len(rooms) != 1 else ""), flush=True)
                del rooms[user.room.code]

    def save_room(self, user, message) -> dict:
        if message["type"] == "save_room":
            return {"type": "save_room", "save_data": user.room.save_room()}

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

