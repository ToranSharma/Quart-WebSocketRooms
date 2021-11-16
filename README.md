# Quart-WebSocketRooms
Quart-WebSocketRooms is a Quart extension that provides a basic API for 'room' based WebSocket Apps.

# Basic Usage
A basic chat room type app would look something like this:
```python
from quart_websocketrooms import WebSocketRooms

app = WebSocketRooms(__name__)

@app.incoming_processing_step("chat_message")
async def chat_message(user, message):
    await user.room.broadcast(message)

app.websocket_rooms_route("/ws")

```
